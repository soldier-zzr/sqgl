const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PORT = process.env.PORT || 8787;
const HOST = "0.0.0.0";
const ROOT = __dirname;
const DB_FILE = path.join(ROOT, "db.json");

const USERS = [
  { username: "admin", password: "123456", role: "admin", displayName: "管理员" },
  { username: "member1", password: "123456", role: "member", displayName: "成员1" },
  { username: "member2", password: "123456", role: "member", displayName: "成员2" },
];

const tokenStore = new Map();

function ensureDb() {
  if (!fs.existsSync(DB_FILE)) {
    fs.writeFileSync(DB_FILE, JSON.stringify({ orders: [] }, null, 2), "utf8");
  }
}

function readDb() {
  ensureDb();
  return JSON.parse(fs.readFileSync(DB_FILE, "utf8"));
}

function writeDb(db) {
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), "utf8");
}

function sendJson(res, code, data) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(data));
}

function unauthorized(res) {
  sendJson(res, 401, { error: "unauthorized" });
}

function notFound(res) {
  sendJson(res, 404, { error: "not_found" });
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

function getAuthUser(req) {
  const auth = String(req.headers.authorization || "");
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  const username = tokenStore.get(token);
  if (!username) return null;
  return USERS.find((u) => u.username === username) || null;
}

function canAccessOrder(user, order) {
  if (!user || !order) return false;
  if (user.role === "admin") return true;
  return order.owner === user.displayName;
}

function serveStatic(req, res) {
  const safePath = decodeURIComponent(req.url.split("?")[0] || "/");
  let filePath = path.join(ROOT, safePath === "/" ? "index.html" : safePath);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(ROOT, "index.html");
  }
  const ext = path.extname(filePath).toLowerCase();
  const typeMap = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
  };
  res.writeHead(200, { "Content-Type": typeMap[ext] || "text/plain; charset=utf-8" });
  fs.createReadStream(filePath).pipe(res);
}

const server = http.createServer(async (req, res) => {
  try {
    const url = req.url.split("?")[0];

    if (req.method === "GET" && url === "/api/health") {
      return sendJson(res, 200, { ok: true, date: new Date().toISOString() });
    }

    if (req.method === "POST" && url === "/api/login") {
      const body = await parseBody(req);
      const username = String(body.username || "").trim();
      const password = String(body.password || "");
      const user = USERS.find((u) => u.username === username && u.password === password);
      if (!user) return unauthorized(res);

      const token = crypto.randomUUID();
      tokenStore.set(token, user.username);
      return sendJson(res, 200, {
        token,
        user: { username: user.username, role: user.role, displayName: user.displayName },
      });
    }

    if (req.method === "GET" && url === "/api/me") {
      const user = getAuthUser(req);
      if (!user) return unauthorized(res);
      return sendJson(res, 200, {
        user: { username: user.username, role: user.role, displayName: user.displayName },
      });
    }

    if (req.method === "GET" && url === "/api/orders") {
      const user = getAuthUser(req);
      if (!user) return unauthorized(res);
      const db = readDb();
      const orders = user.role === "admin" ? db.orders : db.orders.filter((o) => o.owner === user.displayName);
      return sendJson(res, 200, { orders });
    }

    if (req.method === "POST" && url === "/api/orders") {
      const user = getAuthUser(req);
      if (!user) return unauthorized(res);
      const body = await parseBody(req);
      const order = body.order || {};
      if (user.role !== "admin" && order.owner !== user.displayName) {
        return unauthorized(res);
      }
      const db = readDb();
      db.orders.unshift(order);
      writeDb(db);
      return sendJson(res, 200, { ok: true, order });
    }

    if (req.method === "PUT" && url.startsWith("/api/orders/")) {
      const user = getAuthUser(req);
      if (!user) return unauthorized(res);
      const id = decodeURIComponent(url.slice("/api/orders/".length));
      const body = await parseBody(req);
      const nextOrder = body.order || {};
      const db = readDb();
      const idx = db.orders.findIndex((o) => o.id === id);
      if (idx < 0) return notFound(res);
      if (!canAccessOrder(user, db.orders[idx])) return unauthorized(res);
      if (user.role !== "admin" && nextOrder.owner !== user.displayName) return unauthorized(res);
      db.orders[idx] = nextOrder;
      writeDb(db);
      return sendJson(res, 200, { ok: true, order: nextOrder });
    }

    if (req.method === "DELETE" && url.startsWith("/api/orders/")) {
      const user = getAuthUser(req);
      if (!user) return unauthorized(res);
      const id = decodeURIComponent(url.slice("/api/orders/".length));
      const db = readDb();
      const idx = db.orders.findIndex((o) => o.id === id);
      if (idx < 0) return notFound(res);
      if (!canAccessOrder(user, db.orders[idx])) return unauthorized(res);
      db.orders.splice(idx, 1);
      writeDb(db);
      return sendJson(res, 200, { ok: true });
    }

    return serveStatic(req, res);
  } catch (error) {
    return sendJson(res, 500, { error: "server_error", message: String(error.message || error) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Server running at http://127.0.0.1:${PORT}`);
});
