import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";

const redis = new Redis(REDIS_URL, {
  maxRetriesPerRequest: 3,
  retryStrategy(times: number) {
    if (times > 5) return null; // stop retrying
    return Math.min(times * 200, 2000);
  },
});

redis.on("connect", () => {
  console.log(`Redis connected: ${REDIS_URL}`);
});

redis.on("error", (err: Error) => {
  console.error("Redis error:", err.message);
});

export { redis };
export default redis;
