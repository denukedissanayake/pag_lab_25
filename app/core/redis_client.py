import redis

# Connect to Redis. Ensure Redis is running on localhost:6379
# For production, use a more robust configuration management.
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
