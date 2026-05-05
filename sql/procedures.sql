-- Project 2 stored procedures (PL/pgSQL)
-- All application writes should use these functions.

BEGIN;

-- Helper: require condition else raise.
CREATE OR REPLACE FUNCTION _require(cond BOOLEAN, msg TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  IF NOT cond THEN
    RAISE EXCEPTION '%', msg USING ERRCODE = 'P0001';
  END IF;
END;
$$;

-- Auth / registration
CREATE OR REPLACE FUNCTION register_user(
  p_email TEXT,
  p_username TEXT,
  p_nickname TEXT,
  p_password_hash TEXT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  new_id INT;
BEGIN
  INSERT INTO users(email, username, nickname, password_hash)
  VALUES (p_email, p_username, p_nickname, p_password_hash)
  RETURNING user_id INTO new_id;
  RETURN new_id;
END;
$$;

-- Workspace creation: creator becomes admin member
CREATE OR REPLACE FUNCTION create_workspace(
  p_name TEXT,
  p_description TEXT,
  p_creator_id INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  wid INT;
BEGIN
  INSERT INTO workspaces(name, description, created_by)
  VALUES (p_name, p_description, p_creator_id)
  RETURNING workspace_id INTO wid;

  INSERT INTO workspace_members(workspace_id, user_id, is_admin)
  VALUES (wid, p_creator_id, TRUE);

  RETURN wid;
END;
$$;

-- Workspace admin management
CREATE OR REPLACE FUNCTION add_workspace_admin(
  p_workspace_id INT,
  p_actor_id INT,
  p_target_user_id INT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM _require(
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = p_workspace_id
        AND user_id = p_actor_id
        AND is_admin = TRUE
    ),
    'not_authorized'
  );

  PERFORM _require(
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = p_workspace_id
        AND user_id = p_target_user_id
    ),
    'target_not_member'
  );

  UPDATE workspace_members
  SET is_admin = TRUE
  WHERE workspace_id = p_workspace_id
    AND user_id = p_target_user_id;
END;
$$;

-- Workspace update: description (admin only)
CREATE OR REPLACE FUNCTION update_workspace_description(
  p_workspace_id INT,
  p_actor_id INT,
  p_description TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM _require(
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = p_workspace_id
        AND user_id = p_actor_id
        AND is_admin = TRUE
    ),
    'not_authorized'
  );

  UPDATE workspaces
  SET description = p_description
  WHERE workspace_id = p_workspace_id;
END;
$$;

-- Channel creation
CREATE OR REPLACE FUNCTION create_channel(
  p_workspace_id INT,
  p_name TEXT,
  p_type TEXT,
  p_creator_id INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  cid INT;
BEGIN
  PERFORM _require(
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = p_workspace_id
        AND user_id = p_creator_id
    ),
    'not_workspace_member'
  );

  INSERT INTO channels(workspace_id, name, type, created_by)
  VALUES (p_workspace_id, p_name, p_type, p_creator_id)
  RETURNING channel_id INTO cid;

  INSERT INTO channel_members(channel_id, user_id)
  VALUES (cid, p_creator_id)
  ON CONFLICT DO NOTHING;

  INSERT INTO channel_reads(channel_id, user_id, last_read_at)
  VALUES (cid, p_creator_id, CURRENT_TIMESTAMP)
  ON CONFLICT (channel_id, user_id) DO NOTHING;

  RETURN cid;
END;
$$;

-- Direct channel: deterministic name + idempotent lookup
CREATE OR REPLACE FUNCTION create_or_get_direct_channel(
  p_workspace_id INT,
  p_user_a INT,
  p_user_b INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  lo INT;
  hi INT;
  cname TEXT;
  cid INT;
BEGIN
  lo := LEAST(p_user_a, p_user_b);
  hi := GREATEST(p_user_a, p_user_b);

  PERFORM _require(
    lo <> hi,
    'invalid_direct_channel'
  );

  PERFORM _require(
    EXISTS (SELECT 1 FROM workspace_members WHERE workspace_id = p_workspace_id AND user_id = p_user_a),
    'not_workspace_member_a'
  );
  PERFORM _require(
    EXISTS (SELECT 1 FROM workspace_members WHERE workspace_id = p_workspace_id AND user_id = p_user_b),
    'not_workspace_member_b'
  );

  cname := lo::TEXT || '-' || hi::TEXT;

  SELECT channel_id INTO cid
  FROM channels
  WHERE workspace_id = p_workspace_id
    AND type = 'direct'
    AND name = cname;

  IF cid IS NULL THEN
    INSERT INTO channels(workspace_id, name, type, created_by)
    VALUES (p_workspace_id, cname, 'direct', p_user_a)
    RETURNING channel_id INTO cid;
  END IF;

  INSERT INTO channel_members(channel_id, user_id) VALUES (cid, p_user_a)
  ON CONFLICT DO NOTHING;
  INSERT INTO channel_members(channel_id, user_id) VALUES (cid, p_user_b)
  ON CONFLICT DO NOTHING;

  INSERT INTO channel_reads(channel_id, user_id, last_read_at)
  VALUES (cid, p_user_a, CURRENT_TIMESTAMP)
  ON CONFLICT (channel_id, user_id) DO NOTHING;
  INSERT INTO channel_reads(channel_id, user_id, last_read_at)
  VALUES (cid, p_user_b, CURRENT_TIMESTAMP)
  ON CONFLICT (channel_id, user_id) DO NOTHING;

  RETURN cid;
END;
$$;

-- Post message
CREATE OR REPLACE FUNCTION post_message(
  p_channel_id INT,
  p_user_id INT,
  p_content TEXT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  mid INT;
  wid INT;
BEGIN
  SELECT workspace_id INTO wid FROM channels WHERE channel_id = p_channel_id;
  PERFORM _require(wid IS NOT NULL, 'channel_not_found');

  PERFORM _require(
    EXISTS (SELECT 1 FROM workspace_members WHERE workspace_id = wid AND user_id = p_user_id),
    'not_workspace_member'
  );
  PERFORM _require(
    EXISTS (SELECT 1 FROM channel_members WHERE channel_id = p_channel_id AND user_id = p_user_id),
    'not_channel_member'
  );

  INSERT INTO messages(channel_id, user_id, content)
  VALUES (p_channel_id, p_user_id, p_content)
  RETURNING message_id INTO mid;

  -- Consider the author as having read up to now.
  INSERT INTO channel_reads(channel_id, user_id, last_read_at)
  VALUES (p_channel_id, p_user_id, CURRENT_TIMESTAMP)
  ON CONFLICT (channel_id, user_id)
  DO UPDATE SET last_read_at = EXCLUDED.last_read_at;

  RETURN mid;
END;
$$;

-- Mark channel read (used when opening channel)
CREATE OR REPLACE FUNCTION mark_channel_read(
  p_channel_id INT,
  p_user_id INT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  wid INT;
BEGIN
  SELECT workspace_id INTO wid FROM channels WHERE channel_id = p_channel_id;
  PERFORM _require(wid IS NOT NULL, 'channel_not_found');

  PERFORM _require(
    EXISTS (SELECT 1 FROM workspace_members WHERE workspace_id = wid AND user_id = p_user_id),
    'not_workspace_member'
  );
  PERFORM _require(
    EXISTS (SELECT 1 FROM channel_members WHERE channel_id = p_channel_id AND user_id = p_user_id),
    'not_channel_member'
  );

  INSERT INTO channel_reads(channel_id, user_id, last_read_at)
  VALUES (p_channel_id, p_user_id, CURRENT_TIMESTAMP)
  ON CONFLICT (channel_id, user_id)
  DO UPDATE SET last_read_at = EXCLUDED.last_read_at;
END;
$$;

-- Unread counts (per channel, only for channels user belongs to)
CREATE OR REPLACE FUNCTION list_unread_counts(p_user_id INT)
RETURNS TABLE(channel_id INT, unread BIGINT)
LANGUAGE sql
AS $$
  SELECT
    c.channel_id,
    COUNT(m.message_id) AS unread
  FROM channel_members cm
  JOIN channels c ON c.channel_id = cm.channel_id
  LEFT JOIN channel_reads cr
    ON cr.channel_id = c.channel_id AND cr.user_id = cm.user_id
  LEFT JOIN messages m
    ON m.channel_id = c.channel_id
   AND m.created_at > COALESCE(cr.last_read_at, 'epoch'::timestamp)
  WHERE cm.user_id = p_user_id
  GROUP BY c.channel_id
$$;

-- Invitations: workspace
CREATE OR REPLACE FUNCTION invite_to_workspace(
  p_inviter_id INT,
  p_invitee_email TEXT,
  p_workspace_id INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  iid INT;
BEGIN
  PERFORM _require(
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = p_workspace_id
        AND user_id = p_inviter_id
        AND is_admin = TRUE
    ),
    'not_authorized'
  );

  INSERT INTO invitations(inviter_id, invitee_email, workspace_id, channel_id, status)
  VALUES (p_inviter_id, p_invitee_email, p_workspace_id, NULL, 'pending')
  RETURNING invitation_id INTO iid;

  RETURN iid;
END;
$$;

-- Invitations: channel
CREATE OR REPLACE FUNCTION invite_to_channel(
  p_inviter_id INT,
  p_invitee_email TEXT,
  p_channel_id INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  iid INT;
  wid INT;
BEGIN
  SELECT workspace_id INTO wid FROM channels WHERE channel_id = p_channel_id;
  PERFORM _require(wid IS NOT NULL, 'channel_not_found');

  PERFORM _require(
    EXISTS (SELECT 1 FROM channel_members WHERE channel_id = p_channel_id AND user_id = p_inviter_id),
    'not_authorized'
  );

  INSERT INTO invitations(inviter_id, invitee_email, workspace_id, channel_id, status)
  VALUES (p_inviter_id, p_invitee_email, NULL, p_channel_id, 'pending')
  RETURNING invitation_id INTO iid;

  RETURN iid;
END;
$$;

-- Respond to invitation: accept/reject
CREATE OR REPLACE FUNCTION respond_to_invitation(
  p_invitation_id INT,
  p_responder_user_id INT,
  p_action TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  inv RECORD;
  responder_email TEXT;
  wid INT;
  cid INT;
BEGIN
  SELECT email INTO responder_email FROM users WHERE user_id = p_responder_user_id;
  PERFORM _require(responder_email IS NOT NULL, 'user_not_found');

  SELECT * INTO inv FROM invitations WHERE invitation_id = p_invitation_id FOR UPDATE;
  PERFORM _require(inv.invitation_id IS NOT NULL, 'invitation_not_found');
  PERFORM _require(inv.status = 'pending', 'invitation_not_pending');
  PERFORM _require(LOWER(inv.invitee_email) = LOWER(responder_email), 'not_invitee');

  IF p_action = 'rejected' THEN
    UPDATE invitations SET status = 'rejected' WHERE invitation_id = p_invitation_id;
    RETURN;
  END IF;

  PERFORM _require(p_action = 'accepted', 'invalid_action');

  wid := inv.workspace_id;
  cid := inv.channel_id;

  IF wid IS NOT NULL THEN
    INSERT INTO workspace_members(workspace_id, user_id, is_admin)
    VALUES (wid, p_responder_user_id, FALSE)
    ON CONFLICT DO NOTHING;
  ELSIF cid IS NOT NULL THEN
    SELECT workspace_id INTO wid FROM channels WHERE channel_id = cid;
    INSERT INTO workspace_members(workspace_id, user_id, is_admin)
    VALUES (wid, p_responder_user_id, FALSE)
    ON CONFLICT DO NOTHING;

    INSERT INTO channel_members(channel_id, user_id)
    VALUES (cid, p_responder_user_id)
    ON CONFLICT DO NOTHING;

    INSERT INTO channel_reads(channel_id, user_id, last_read_at)
    VALUES (cid, p_responder_user_id, CURRENT_TIMESTAMP)
    ON CONFLICT (channel_id, user_id) DO NOTHING;
  ELSE
    PERFORM _require(FALSE, 'invalid_invitation_target');
  END IF;

  UPDATE invitations SET status = 'accepted' WHERE invitation_id = p_invitation_id;
END;
$$;

-- Reactions
CREATE OR REPLACE FUNCTION toggle_reaction(
  p_message_id INT,
  p_user_id INT,
  p_emoji TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  cid INT;
  wid INT;
BEGIN
  SELECT channel_id INTO cid FROM messages WHERE message_id = p_message_id;
  PERFORM _require(cid IS NOT NULL, 'message_not_found');
  SELECT workspace_id INTO wid FROM channels WHERE channel_id = cid;

  PERFORM _require(
    EXISTS (SELECT 1 FROM workspace_members WHERE workspace_id = wid AND user_id = p_user_id),
    'not_workspace_member'
  );
  PERFORM _require(
    EXISTS (SELECT 1 FROM channel_members WHERE channel_id = cid AND user_id = p_user_id),
    'not_channel_member'
  );

  IF EXISTS (
    SELECT 1 FROM reactions
    WHERE message_id = p_message_id AND user_id = p_user_id AND emoji = p_emoji
  ) THEN
    DELETE FROM reactions
    WHERE message_id = p_message_id AND user_id = p_user_id AND emoji = p_emoji;
  ELSE
    INSERT INTO reactions(message_id, user_id, emoji)
    VALUES (p_message_id, p_user_id, p_emoji);
  END IF;
END;
$$;

-- Search visible messages (permission-aware)
CREATE OR REPLACE FUNCTION search_visible_messages(
  p_user_id INT,
  p_keyword TEXT
)
RETURNS TABLE(
  message_id INT,
  workspace_id INT,
  workspace_name TEXT,
  channel_id INT,
  channel_name TEXT,
  author_username TEXT,
  content TEXT,
  created_at TIMESTAMP
)
LANGUAGE sql
AS $$
  SELECT
    m.message_id,
    w.workspace_id,
    w.name AS workspace_name,
    c.channel_id,
    c.name AS channel_name,
    u.username AS author_username,
    m.content,
    m.created_at
  FROM messages m
  JOIN channels c ON c.channel_id = m.channel_id
  JOIN workspaces w ON w.workspace_id = c.workspace_id
  JOIN users u ON u.user_id = m.user_id
  JOIN channel_members cm
    ON cm.channel_id = c.channel_id
   AND cm.user_id = p_user_id
  JOIN workspace_members wm
    ON wm.workspace_id = c.workspace_id
   AND wm.user_id = p_user_id
  WHERE m.content ILIKE '%' || p_keyword || '%'
  ORDER BY m.created_at DESC, m.message_id DESC
$$;

COMMIT;

