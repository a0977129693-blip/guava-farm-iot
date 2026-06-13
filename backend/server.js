const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');

const app = express();
app.use(cors());
app.use(express.json());

// =======================================================
// 🔐 安全加密防護：從 Render 的環境變數中安全讀取憑證
// =======================================================
const serviceAccount = {
  type: "service_account",
  project_id: process.env.FIREBASE_PROJECT_ID,
  privateKey: process.env.FIREBASE_PRIVATE_KEY ? process.env.FIREBASE_PRIVATE_KEY.replace(/\\n/g, '\n') : undefined,
  clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
};

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: process.env.FIREBASE_DATABASE_URL // 從環境變數讀取資料庫網址
});

const db = admin.database();

// 接收 Wokwi 資料的 API 節點
app.post('/api/data', async (req, res) => {
  try {
    const telemetry = req.body;
    const timestamp = Date.now();
    const dataWithTime = {
      ...telemetry,
      createdAt: timestamp
    };

    await db.ref('orchard_data/current').set(dataWithTime);
    await db.ref('orchard_data/history').push(dataWithTime);

    // 限制歷史紀錄總數不超過 50 筆，節省 Firebase 免費額度
    const historyRef = db.ref('orchard_data/history');
    const snapshot = await historyRef.once('value');
    if (snapshot.exists() && Object.keys(snapshot.val()).length > 50) {
      const keys = Object.keys(snapshot.val());
      await historyRef.child(keys[0]).remove();
    }

    console.log("✅ 資料已成功同步至 Firebase");
    res.status(200).json({ status: "success" });
  } catch (error) {
    console.error("❌ 後端處理失敗:", error);
    res.status(500).json({ status: "error", message: error.message });
  }
});

app.get('/', (req, res) => {
  res.send('Guava Farm IoT Backend is running securely.');
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 後端伺服器正運行於通訊埠 ${PORT}`);
});
