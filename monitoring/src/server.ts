import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import mongoose from 'mongoose';
import { logRoutes } from './routes/logRoutes';

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    methods: ['GET', 'POST']
  }
});

mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/logs');

app.use(express.json());
app.use('/api/logs', logRoutes);

// WebSocket接続処理
io.on('connection', (socket) => {
  console.log('Client connected');
  
  socket.on('subscribe', (filters) => {
    // フィルター条件に基づいてログストリームを開始
  });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

const PORT = process.env.PORT || 4000;
httpServer.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
