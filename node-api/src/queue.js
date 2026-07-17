import { Queue } from "bullmq";
import "dotenv/config";

const connection = { url: process.env.REDIS_URL };

export const documentQueue = new Queue("document-processing", { connection });
export const queueConnection = connection;