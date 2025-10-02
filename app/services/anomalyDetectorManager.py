import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel
from collections import defaultdict
from threading import Lock

# Pydantic model for request body
class LogRequest(BaseModel):
    log_text: str

# ----------------------------
# 2. Model and State Management
# ----------------------------
class AnomalyDetectorManager:
    """A thread-safe class to manage the model, its state, and the adaptive logic."""
    def __init__(self, model_path="app/models/anomaly_model_state.pth"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        # --- Load foundational models (Transformer) ---
        self.tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self.encoder_model = AutoModel.from_pretrained("distilbert-base-uncased").to(self.device)
        self.encoder_model.eval()

        # --- Define Autoencoder architecture ---
        # It must be the same as the one used for training
        class AutoEncoder(nn.Module):
            def __init__(self, input_dim=768, bottleneck=128):
                super().__init__()
                self.encoder = nn.Sequential(nn.Linear(input_dim, 512), nn.ReLU(), nn.Linear(512, bottleneck), nn.ReLU())
                self.decoder = nn.Sequential(nn.Linear(bottleneck, 512), nn.ReLU(), nn.Linear(512, input_dim))
            def forward(self, x):
                return self.decoder(self.encoder(x))

        self.ae = AutoEncoder().to(self.device)
        self.criterion = nn.MSELoss()
        
        # --- Load trained state ---
        try:
            artifacts = torch.load(model_path, map_location=self.device, weights_only=False)
            self.ae.load_state_dict(artifacts['autoencoder_state_dict'])
            self.normals = artifacts['initial_normals'].to(self.device)
            self.threshold = artifacts['anomaly_threshold']
            self.dynamic_known_endpoints = artifacts['known_endpoints']
            self.ae.eval()
            print("✅ Model artifacts loaded successfully.")
        except FileNotFoundError:
            print(f"❌ Error: Model file not found at {model_path}. The API will not work.")
            # Handle this gracefully in a real app, maybe by disabling the endpoint
            self.ae = None


        # --- State for adaptive learning ---
        self.new_endpoint_buffer = defaultdict(list)
        self.PROMOTE_BUFFER_SIZE = 50
        self.lock = Lock() # For thread-safe updates to the model state

    def get_embedding(self, text: str):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding="max_length", max_length=64).to(self.device)
        with torch.no_grad():
            outputs = self.encoder_model(**inputs)
            mean_vec = outputs.last_hidden_state.mean(dim=1)
        return mean_vec.squeeze(0)

    def detect(self, emb_tensor):
        self.ae.eval()
        with torch.no_grad():
            recon = self.ae(emb_tensor.to(self.device))
            err = F.mse_loss(recon, emb_tensor.to(self.device), reduction="none").mean(dim=1)
        return err.cpu().numpy()

    def handle_incoming_log(self, text: str):
        if not self.ae:
            return {"error": "Model not loaded."}
            
        endpoint = text.split(" ")[0].replace("endpoint=", "")
        status_strs = [x.split("=")[1] for x in text.split(" ") if x.startswith("status=")]
        status = int(status_strs[0]) if status_strs else 200

        emb = self.get_embedding(text).unsqueeze(0)
        err = self.detect(emb)[0]

        if endpoint in self.dynamic_known_endpoints:
            pred = "normal" if err <= self.threshold else "anomaly"
            return {"log": text, "recon_error": float(err), "decision": pred, "status": "known_endpoint"}

        # --- Adaptive Logic for Unknown Endpoints ---
        # This part modifies the shared state, so we use a lock
        with self.lock:
            if status == 200:
                self.new_endpoint_buffer[endpoint].append(emb.squeeze(0))
                pred = "normal"

                if len(self.new_endpoint_buffer[endpoint]) >= self.PROMOTE_BUFFER_SIZE:
                    print(f"Promoting {endpoint} and fine-tuning AE...")
                    self.dynamic_known_endpoints.add(endpoint)
                    
                    new_embeds = torch.stack(self.new_endpoint_buffer[endpoint]).to(self.device)
                    self.normals = torch.cat([self.normals, new_embeds])

                    # Fine-tune
                    optimizer = torch.optim.Adam(self.ae.parameters(), lr=1e-4) # Use a smaller learning rate
                    self.ae.train()
                    for _ in range(5):
                        optimizer.zero_grad()
                        recon = self.ae(self.normals)
                        loss = self.criterion(recon, self.normals)
                        loss.backward()
                        optimizer.step()
                    
                    # Recompute threshold
                    self.ae.eval()
                    with torch.no_grad():
                        recon = self.ae(self.normals)
                        errs = F.mse_loss(recon, self.normals, reduction="none").mean(dim=1).cpu().numpy()
                    self.threshold = np.percentile(errs, 95)
                    print(f"Updated anomaly threshold: {self.threshold:.6f}")

                    self.new_endpoint_buffer[endpoint] = [] # Clear buffer
                    status_msg = f"endpoint_promoted_and_model_retrained"
                else:
                    status_msg = f"endpoint_buffered ({len(self.new_endpoint_buffer[endpoint])}/{self.PROMOTE_BUFFER_SIZE})"

            else: # Unknown endpoint with error status
                pred = "anomaly"
                status_msg = "unknown_endpoint_error"
        
        return {"log": text, "recon_error": float(err), "decision": pred, "status": status_msg}