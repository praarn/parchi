import { Router } from "express";
import multer from "multer";
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { pool } from "../db.js";
import { documentQueue } from "../queue.js";
import { callAiService } from "../aiServiceClient.js";

export const documentsRouter = Router();

const uploadDir = path.resolve(process.env.UPLOAD_DIR || "./uploads");
console.log(`[documents] storing uploads in: ${uploadDir}`);
fs.mkdirSync(uploadDir, { recursive: true });

// NOTE: the plan's target architecture uses a signed S3 URL so large files
// upload directly to object storage without proxying through the API.
// For local dev this uses disk storage behind the same /documents/upload
// endpoint; swap this multer config for an S3 presigned-URL flow
// (@aws-sdk/client-s3 getSignedUrl) when you're ready to deploy.
const upload = multer({
  storage: multer.diskStorage({
    destination: uploadDir,
    filename: (req, file, cb) => cb(null, `${crypto.randomUUID()}.pdf`),
  }),
  limits: { fileSize: 50 * 1024 * 1024 }, // 50MB — scanned multi-page govt PDFs can be large
  fileFilter: (req, file, cb) => {
    if (file.mimetype !== "application/pdf") {
      return cb(new Error("Only PDF files are accepted"));
    }
    cb(null, true);
  },
});

documentsRouter.post("/upload", upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });

  const fileBuffer = fs.readFileSync(req.file.path);
  const file_hash = crypto.createHash("sha256").update(fileBuffer).digest("hex");

  // Dedup: identical document already processed -> short-circuit (plan §4.3)
  const existing = await pool.query("SELECT * FROM documents WHERE file_hash = $1", [file_hash]);
  if (existing.rows.length > 0) {
    fs.unlinkSync(req.file.path); // don't keep a duplicate copy on disk
    return res.status(200).json({ document: existing.rows[0], deduped: true });
  }

  const result = await pool.query(
    `INSERT INTO documents (user_id, file_url, file_hash, original_filename, status)
     VALUES ($1, $2, $3, $4, 'uploaded') RETURNING *`,
    [req.user.sub, req.file.path, file_hash, req.file.originalname]
  );
  res.status(201).json({ document: result.rows[0], deduped: false });
});

documentsRouter.post("/:id/process", async (req, res) => {
  const { id } = req.params;
  const doc = await pool.query("SELECT * FROM documents WHERE id = $1 AND user_id = $2", [id, req.user.sub]);
  if (doc.rows.length === 0) return res.status(404).json({ error: "Document not found" });

  await pool.query("UPDATE documents SET status = 'processing' WHERE id = $1", [id]);
  await documentQueue.add("process-document", {
    documentId: id,
    pdfPath: doc.rows[0].file_url,
  });
  res.json({ status: "processing" });
});

documentsRouter.get("/:id", async (req, res) => {
  const { id } = req.params;
  const doc = await pool.query("SELECT * FROM documents WHERE id = $1 AND user_id = $2", [id, req.user.sub]);
  if (doc.rows.length === 0) return res.status(404).json({ error: "Document not found" });

  const language = req.query.language || "en";
  const insight = await pool.query(
    "SELECT * FROM document_insights WHERE document_id = $1 AND language = $2",
    [id, language]
  );
  res.json({ document: doc.rows[0], insight: insight.rows[0] || null });
});

documentsRouter.get("/", async (req, res) => {
  const docs = await pool.query(
    "SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC",
    [req.user.sub]
  );
  res.json({ documents: docs.rows });
});

documentsRouter.post("/:id/translate", async (req, res) => {
  const { id } = req.params;
  const { language } = req.body;
  if (!language) return res.status(400).json({ error: "language is required" });

  // Cache hit: already translated for this document+language (plan §3.4/§11)
  const cached = await pool.query(
    "SELECT * FROM document_insights WHERE document_id = $1 AND language = $2",
    [id, language]
  );
  if (cached.rows.length > 0) {
    return res.json({ insight: cached.rows[0], cached: true });
  }

  const english = await pool.query(
    "SELECT * FROM document_insights WHERE document_id = $1 AND language = 'en'",
    [id]
  );
  if (english.rows.length === 0) {
    return res.status(409).json({ error: "Document must finish processing (English) before translation" });
  }

  const translated = await callAiService("/internal/translate", {
    insight: english.rows[0],
    language,
  });

  const inserted = await pool.query(
    `INSERT INTO document_insights (document_id, language, summary, key_points, deadlines, eligibility, explain_like_10)
     VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *`,
    [
      id,
      language,
      translated.summary,
      JSON.stringify(translated.key_points || []),
      JSON.stringify(translated.deadlines || []),
      JSON.stringify(translated.eligibility || {}),
      translated.explain_like_10,
    ]
  );
  res.json({ insight: inserted.rows[0], cached: false });
});

documentsRouter.post("/:id/share", async (req, res) => {
  const { id } = req.params;
  const insight = await pool.query(
    `SELECT summary FROM document_insights WHERE document_id = $1 AND language = $2`,
    [id, req.query.language || "en"]
  );
  const summary = insight.rows[0]?.summary || "Check out this document summary.";
  const text = encodeURIComponent(`${summary}\n\nView full details: ${req.protocol}://${req.get("host")}/document/${id}`);
  res.json({ whatsapp_url: `https://wa.me/?text=${text}` });
});