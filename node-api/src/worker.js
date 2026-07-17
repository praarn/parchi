import { Worker } from "bullmq";
import "dotenv/config";
import { pool } from "./db.js";
import { queueConnection } from "./queue.js";
import { callAiService } from "./aiServiceClient.js";

const worker = new Worker(
  "document-processing",
  async (job) => {
    const { documentId, pdfPath } = job.data;
    console.log(`[worker] processing document ${documentId}`);

    try {
      const result = await callAiService("/internal/process", {
        document_id: documentId,
        pdf_path: pdfPath,
      });

      const insight = result.insight;
      await pool.query(
        `INSERT INTO document_insights (document_id, language, summary, key_points, deadlines, eligibility, explain_like_10)
         VALUES ($1, 'en', $2, $3, $4, $5, $6)
         ON CONFLICT (document_id, language) DO UPDATE SET
           summary = EXCLUDED.summary,
           key_points = EXCLUDED.key_points,
           deadlines = EXCLUDED.deadlines,
           eligibility = EXCLUDED.eligibility,
           explain_like_10 = EXCLUDED.explain_like_10`,
        [
          documentId,
          insight.summary,
          JSON.stringify(insight.key_points || []),
          JSON.stringify(insight.deadlines || []),
          JSON.stringify(insight.eligibility || {}),
          insight.explain_like_10,
        ]
      );

      await pool.query(
        "UPDATE documents SET status = 'ready', page_count = $2 WHERE id = $1",
        [documentId, result.page_count]
      );
      console.log(`[worker] document ${documentId} ready`);
    } catch (err) {
      console.error(`[worker] document ${documentId} failed:`, err.message);
      await pool.query("UPDATE documents SET status = 'failed' WHERE id = $1", [documentId]);
      throw err;
    }
  },
  { connection: queueConnection }
);

worker.on("failed", (job, err) => {
  console.error(`[worker] job ${job.id} failed permanently:`, err.message);
});

console.log("[worker] listening for document-processing jobs");