import express from "express";
import cors from "cors";
import "dotenv/config";

import { authRouter } from "./routes/auth.js";
import { documentsRouter } from "./routes/documents.js";
import { chatRouter } from "./routes/chat.js";
import { requireAuth } from "./middleware/auth.js";

const app = express();
app.use(cors());
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.use("/auth", authRouter);
app.use("/documents", requireAuth, documentsRouter);
app.use("/documents", requireAuth, chatRouter);

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ error: err.message || "Internal server error" });
});

const port = process.env.PORT || 4000;
app.listen(port, () => console.log(`[api] listening on port ${port}`));