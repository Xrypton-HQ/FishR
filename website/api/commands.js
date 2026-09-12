/**
 * Vercel Serverless Function - FishR Commands API (Supabase version)
 *
 * POST /api/commands   → Bot updates the command list (stores in Supabase)
 * GET  /api/commands   → Website fetches the latest commands from Supabase
 *
 * Required Environment Variables (set in Vercel dashboard):
 *   SUPABASE_URL=https://your-project.supabase.co
 *   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
 *   FISHR_UPDATE_SECRET=your-strong-secret-here
 *
 * Table to create in Supabase (SQL):
 *   CREATE TABLE bot_commands (
 *     id TEXT PRIMARY KEY DEFAULT 'latest',
 *     data JSONB,
 *     updated_at TIMESTAMPTZ DEFAULT NOW()
 *   );
 */

const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

const UPDATE_SECRET = process.env.FISHR_UPDATE_SECRET || 'change-me-in-production';
const TABLE = 'bot_commands';
const ROW_ID = 'latest';

module.exports = async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-fishr-secret');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method === 'POST') {
    const auth = req.headers['x-fishr-secret'];
    if (auth !== UPDATE_SECRET) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
      const body = req.body;

      let payloadToStore;
      if (body.categories) {
        payloadToStore = { type: 'categories', data: body.categories };
      } else if (body.commands && Array.isArray(body.commands)) {
        payloadToStore = { type: 'flat', data: body.commands };
      } else {
        payloadToStore = { type: 'raw', data: body };
      }

      const { error } = await supabase
        .from(TABLE)
        .upsert({
          id: ROW_ID,
          data: payloadToStore,
          updated_at: new Date().toISOString()
        });

      if (error) {
        console.error('Supabase upsert error:', error);
        return res.status(500).json({ error: 'Failed to store commands in Supabase' });
      }

      return res.status(200).json({
        success: true,
        message: 'Commands updated in Supabase',
        storedAt: new Date().toISOString()
      });
    } catch (err) {
      console.error('Supabase write error:', err);
      return res.status(500).json({ error: 'Failed to store commands' });
    }
  }

  if (req.method === 'GET') {
    try {
      const { data, error } = await supabase
        .from(TABLE)
        .select('data, updated_at')
        .eq('id', ROW_ID)
        .single();

      if (error || !data) {
        return res.status(200).json({
          type: 'empty',
          data: {},
          message: 'No commands stored yet. Bot has not synced.'
        });
      }

      return res.status(200).json(data.data);
    } catch (err) {
      console.error('Supabase read error:', err);
      return res.status(500).json({ error: 'Failed to retrieve commands' });
    }
  }

  res.setHeader('Allow', ['GET', 'POST']);
  return res.status(405).json({ error: 'Method not allowed' });
};
