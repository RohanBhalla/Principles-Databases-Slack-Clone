-- Project 2 schema (revised from Project 1)
-- Safe to re-run: drops objects in dependency order.

BEGIN;

DROP TABLE IF EXISTS reactions CASCADE;
DROP TABLE IF EXISTS channel_reads CASCADE;
DROP TABLE IF EXISTS invitations CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS channel_members CASCADE;
DROP TABLE IF EXISTS channels CASCADE;
DROP TABLE IF EXISTS workspace_members CASCADE;
DROP TABLE IF EXISTS workspaces CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Users Table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    nickname VARCHAR(50),
    -- bcrypt hash (typically 60 chars), but keep a little headroom.
    password_hash VARCHAR(255) NOT NULL
);

-- Workspaces Table
CREATE TABLE workspaces (
    workspace_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT NOT NULL,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE RESTRICT
);

-- Workspace Members Table (Many-to-Many Relationship)
CREATE TABLE workspace_members (
    workspace_id INT NOT NULL,
    user_id INT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Channels Table
CREATE TABLE channels (
    channel_id SERIAL PRIMARY KEY,
    workspace_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('public', 'private', 'direct')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, name)
);

-- Channel Members Table (Many-to-Many Relationship)
CREATE TABLE channel_members (
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, user_id),
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Messages Table
CREATE TABLE messages (
    message_id SERIAL PRIMARY KEY,
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Invitations Table
CREATE TABLE invitations (
    invitation_id SERIAL PRIMARY KEY,
    inviter_id INT NOT NULL,
    invitee_email VARCHAR(255) NOT NULL,
    workspace_id INT,
    channel_id INT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inviter_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE,
    CHECK (
        (workspace_id IS NOT NULL AND channel_id IS NULL) OR
        (workspace_id IS NULL AND channel_id IS NOT NULL)
    )
);

-- Prevent duplicate pending invites to the same target.
CREATE UNIQUE INDEX uniq_pending_invite
  ON invitations (LOWER(invitee_email), COALESCE(workspace_id, 0), COALESCE(channel_id, 0))
  WHERE status = 'pending';

-- Extra feature: unread counts (per user per channel)
CREATE TABLE channel_reads (
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, user_id),
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Extra feature: emoji reactions
CREATE TABLE reactions (
    message_id INT NOT NULL,
    user_id INT NOT NULL,
    emoji VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (message_id, user_id, emoji),
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX idx_messages_channel_created_at ON messages(channel_id, created_at DESC, message_id DESC);
CREATE INDEX idx_invitations_email_status ON invitations(LOWER(invitee_email), status);
CREATE INDEX idx_channel_members_user ON channel_members(user_id);
CREATE INDEX idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX idx_reactions_message ON reactions(message_id);

COMMIT;

