import { Router } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { pool } from "../db.js";

export const authRouter = Router();

function issueToken(user) {
  return jwt.sign(
    { sub: user.id, email: user.email },
    process.env.JWT_SECRET,
    { expiresIn: "15m" }
  );
}

authRouter.post("/signup", async (req, res) => {
  const { email, password, name, preferred_language } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: "email and password are required" });
  }
  const existing = await pool.query("SELECT id FROM users WHERE email = $1", [email]);
  if (existing.rows.length > 0) {
    return res.status(409).json({ error: "An account with that email already exists" });
  }
  const password_hash = await bcrypt.hash(password, 10);
  const result = await pool.query(
    `INSERT INTO users (email, password_hash, name, preferred_language)
     VALUES ($1, $2, $3, $4) RETURNING id, email, name, preferred_language`,
    [email, password_hash, name || null, preferred_language || "en"]
  );
  const user = result.rows[0];
  res.status(201).json({ user, token: issueToken(user) });
});

authRouter.post("/login", async (req, res) => {
  const { email, password } = req.body;
  const result = await pool.query("SELECT * FROM users WHERE email = $1", [email]);
  const user = result.rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: "Invalid email or password" });
  }
  res.json({
    user: { id: user.id, email: user.email, name: user.name, preferred_language: user.preferred_language },
    token: issueToken(user),
  });
});