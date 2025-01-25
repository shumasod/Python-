import mongoose from 'mongoose';

const LogSchema = new mongoose.Schema({
  timestamp: {
    type: Date,
    default: Date.now
  },
  level: {
    type: String,
    enum: ['INFO', 'WARN', 'ERROR'],
    required: true
  },
  message: {
    type: String,
    required: true
  },
  source: String,
  metadata: mongoose.Schema.Types.Mixed
}, { timestamps: true });

export const Log = mongoose.model('Log', LogSchema);
