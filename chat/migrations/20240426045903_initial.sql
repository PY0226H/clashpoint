-- foundation schema for chat + auth core

-- create user table
CREATE TABLE users(
  id bigserial PRIMARY KEY,
  fullname varchar(64) NOT NULL,
  email varchar(64),
  -- hashed argon2 password, length 97
  password_hash varchar(97) NOT NULL,
  token_version bigint NOT NULL DEFAULT 0,
  phone_e164 varchar(20),
  phone_verified_at timestamptz,
  phone_bind_required boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users(id, fullname, email, password_hash)
  VALUES (0, 'super user', 'super@none.org', '')
ON CONFLICT (id) DO NOTHING;

-- create index for users for email
CREATE UNIQUE INDEX email_index ON users(email);

-- phone is optional, but must be globally unique when provided
CREATE UNIQUE INDEX users_phone_e164_unique_idx
  ON users(phone_e164)
  WHERE phone_e164 IS NOT NULL;

-- create chat type: single, group, private_channel, public_channel
CREATE TYPE chat_type AS ENUM(
  'single',
  'group',
  'private_channel',
  'public_channel'
);

-- create chat table
CREATE TABLE chats(
  id bigserial PRIMARY KEY,
  name varchar(64),
  type chat_type NOT NULL,
  -- user id list
  members bigint[] NOT NULL,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (name, members)
);

-- create message table
CREATE TABLE messages(
  id bigserial PRIMARY KEY,
  chat_id bigint NOT NULL REFERENCES chats(id),
  sender_id bigint NOT NULL REFERENCES users(id),
  content text NOT NULL,
  files text[] DEFAULT '{}',
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

-- create index for messages for chat_id and created_at order by created_at desc
CREATE INDEX chat_id_created_at_index ON messages(chat_id, created_at DESC);

-- create index for messages for sender_id
CREATE INDEX sender_id_index ON messages(sender_id, created_at DESC);

-- create index for chat members
CREATE INDEX chat_members_index ON chats USING GIN(members);
