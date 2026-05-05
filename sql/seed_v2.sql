-- Seed demo data for Project 2 (matches Project 1 narrative)
-- Assumes schema_v2.sql already applied.

BEGIN;

-- Use pgcrypto for bcrypt hashing directly in SQL.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

TRUNCATE TABLE reactions, channel_reads, invitations, messages, channel_members, channels, workspace_members, workspaces, users
RESTART IDENTITY CASCADE;

-- Users (password for all demo accounts: password123)
INSERT INTO users (email, username, nickname, password_hash) VALUES
  ('rohan@example.com',   'rbhalla',  'Rohan',   crypt('password123', gen_salt('bf', 12))),
  ('akshat@example.com',  'asaini',   'Akshat',  crypt('password123', gen_salt('bf', 12))),
  ('aman@example.com',    'asingh',   'Aman',    crypt('password123', gen_salt('bf', 12))),
  ('ekaansh@example.com', 'easports', 'Ekaansh', crypt('password123', gen_salt('bf', 12))),
  ('ishaan@example.com',  'ishaan',   'Ishaan',  crypt('password123', gen_salt('bf', 12)));

-- Workspaces
INSERT INTO workspaces (name, description, created_by) VALUES
  ('SchoolFriends', 'Friends from school', 1),
  ('WorkSlack', 'Work workspace', 1),
  ('Obeano', 'Side project workspace', 1);

-- workspace_id: 1 SchoolFriends, 2 WorkSlack, 3 Obeano
INSERT INTO workspace_members (workspace_id, user_id, is_admin) VALUES
  (1, 1, FALSE),
  (1, 4, TRUE),
  (1, 3, FALSE),
  (1, 5, FALSE),
  (2, 1, FALSE),
  (2, 2, FALSE),
  (3, 1, TRUE),
  (3, 2, TRUE);

-- Channels
INSERT INTO channels (workspace_id, name, type, created_by) VALUES
  (1, 'Gaming', 'public', 1),
  (1, 'USBased', 'private', 1),
  (1, 'rohan-ekaansh', 'direct', 1),
  (2, 'akshat-rohan', 'direct', 1);

-- channel_id order: 1 Gaming, 2 USBased, 3 rohan-ekaansh, 4 akshat-rohan
INSERT INTO channel_members (channel_id, user_id) VALUES
  (1, 1), (1, 3), (1, 4),
  (2, 1), (2, 3),
  (3, 1), (3, 4),
  (4, 1), (4, 2);

-- Messages (explicit times for chronological demos)
INSERT INTO messages (channel_id, user_id, content, created_at) VALUES
  (3, 1, 'Aman is ghosting messages', '2026-04-20 09:00:00'),
  (1, 4, 'Who all are free for fortnite tonight?', '2026-04-21 10:00:00'),
  (1, 3, 'I''m busy', '2026-04-21 10:05:00'),
  (1, 1, 'I''m free', '2026-04-21 10:10:00'),
  (4, 2, 'found a bug in code, pushing a fix shortly', '2026-04-21 15:00:00'),
  (1, 4, 'The ramp is perpendicular to the floor in fortnite builds', '2026-04-21 11:00:00');

-- Invitations (pending)
INSERT INTO invitations (inviter_id, invitee_email, workspace_id, channel_id, status, created_at) VALUES
  (4, 'rohan@example.com', 1, NULL, 'pending', '2026-04-18 12:00:00'),
  (4, 'aman@example.com', 1, NULL, 'pending', '2026-04-18 12:05:00');

INSERT INTO invitations (inviter_id, invitee_email, workspace_id, channel_id, status, created_at) VALUES
  (4, 'ishaan@example.com', NULL, 1, 'pending', '2026-04-10 10:00:00'),
  (1, 'outsider@example.com', NULL, 1, 'pending', '2026-04-08 08:00:00');

-- Seed reads: make Rohan appear to have unread in Gaming (last read before last msg)
INSERT INTO channel_reads(channel_id, user_id, last_read_at) VALUES
  (1, 1, '2026-04-21 10:06:00'),  -- Rohan hasn't read the later messages yet
  (1, 3, '2026-04-21 11:05:00'),  -- Aman has read through everything
  (1, 4, '2026-04-21 10:30:00'),  -- Ekaansh has unread (perpendicular msg at 11)
  (2, 1, '2026-04-21 10:00:00'),
  (2, 3, '2026-04-21 10:00:00'),
  (3, 1, '2026-04-20 09:30:00'),
  (3, 4, '2026-04-20 09:30:00'),
  (4, 1, '2026-04-21 15:05:00'),
  (4, 2, '2026-04-21 15:05:00');

-- Seed some reactions for demo
-- message_id order follows inserts above: 1..6
INSERT INTO reactions(message_id, user_id, emoji) VALUES
  (2, 1, '👍'),
  (2, 3, '👍'),
  (2, 4, '🎉'),
  (6, 1, '😂'),
  (6, 4, '✅');

COMMIT;

