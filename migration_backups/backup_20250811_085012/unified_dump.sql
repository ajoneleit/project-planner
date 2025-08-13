BEGIN TRANSACTION;
CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT DEFAULT 'anonymous',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
INSERT INTO "conversations" VALUES(1,'test-project','user','Hello','2025-08-08T11:24:24.532342','test-user','{}','2025-08-08 15:24:24');
INSERT INTO "conversations" VALUES(2,'test-project','assistant','Hi there\!','2025-08-08T11:24:24.547068','test-user','{}','2025-08-08 15:24:24');
INSERT INTO "conversations" VALUES(3,'test-conversation','user','Hello test','2025-08-08T11:26:31.909055','test-user','{}','2025-08-08 15:26:31');
INSERT INTO "conversations" VALUES(4,'test-reference-project:test-user','user','I need help with my web application project','2025-08-08T11:29:25.445141','test-user','{}','2025-08-08 15:29:25');
INSERT INTO "conversations" VALUES(5,'test-reference-project:test-user','assistant','Got it, you''re working on a web application project. What specific aspects do you need help with? Are you looking for guidance on objectives, technical requirements, or something else?','2025-08-08T11:29:25.463337','test-user','{}','2025-08-08 15:29:25');
INSERT INTO "conversations" VALUES(6,'test-reference-project:test-user','user','Add the features you just mentioned to my project','2025-08-08T11:29:51.868599','test-user','{}','2025-08-08 15:29:51');
INSERT INTO "conversations" VALUES(7,'test-reference-project:test-user','assistant','Got it, I''ve noted the features you mentioned. What specific features are you referring to, and can you provide any details on their functionality or importance?','2025-08-08T11:29:51.887701','test-user','{}','2025-08-08 15:29:51');
INSERT INTO "conversations" VALUES(8,'test-reference-project:test-user','user','Can you list the features you previously mentioned?','2025-08-08T11:33:01.779729','test-user','{}','2025-08-08 15:33:01');
INSERT INTO "conversations" VALUES(9,'test-reference-project:test-user','assistant','It looks like we haven''t discussed specific features yet in this conversation. To help define the features for the Test Reference Project, could you share what functionalities you envision? What user needs or specifications should these features address?','2025-08-08T11:33:01.794423','test-user','{}','2025-08-08 15:33:01');
INSERT INTO "conversations" VALUES(10,'test-reference-project:test-user','user','What were the main points we discussed earlier?','2025-08-08T11:34:22.914001','test-user','{}','2025-08-08 15:34:22');
INSERT INTO "conversations" VALUES(11,'test-reference-project:test-user','assistant','It looks like there isn''t any previous conversation history available for this project yet. However, we can start discussing the key aspects of the Test Reference Project. 

To get us going, could you share what specific objectives or success criteria you have in mind for this project? Additionally, are there any particular challenges or constraints you''re currently facing?','2025-08-08T11:34:22.932685','test-user','{}','2025-08-08 15:34:22');
INSERT INTO "conversations" VALUES(12,'test-reference-project:test-user','user','Can you summarize what we talked about before?','2025-08-08T11:36:46.476246','test-user','{}','2025-08-08 15:36:46');
INSERT INTO "conversations" VALUES(13,'test-reference-project:test-user','assistant','It looks like there isn''t any previous conversation history available for this project. However, I can help you get started by discussing the objectives, requirements, or any specific challenges you''re facing with the Test Reference Project. What would you like to focus on today?','2025-08-08T11:36:46.491470','test-user','{}','2025-08-08 15:36:46');
INSERT INTO "conversations" VALUES(14,'test-reference-project:test-user','user','Now reference our previous discussion about features','2025-08-08T11:39:10.732600','test-user','{}','2025-08-08 15:39:10');
INSERT INTO "conversations" VALUES(15,'test-reference-project:test-user','assistant','Got it, you''re referring to our earlier discussion about features for the Test Reference Project. What specific aspects of those features would you like to explore further? Are there any particular functionalities or user specifications you want to clarify?','2025-08-08T11:39:10.752048','test-user','{}','2025-08-08 15:39:10');
INSERT INTO "conversations" VALUES(16,'test-conversation-project:test-user','user','Hello, this is a test message','2025-08-11T08:36:48.282879','test-user','{}','2025-08-11 12:36:48');
INSERT INTO "conversations" VALUES(17,'test-conversation-project:test-user','assistant','Hello! I understand this is a test. How can I help you?','2025-08-11T08:36:48.298161','test-user','{}','2025-08-11 12:36:48');
INSERT INTO "conversations" VALUES(18,'test-conversation-project:test-user','user','Hello, this is a test message','2025-08-11T08:40:37.361070','test-user','{}','2025-08-11 12:40:37');
INSERT INTO "conversations" VALUES(19,'test-conversation-project:test-user','assistant','Hello! I understand this is a test. How can I help you?','2025-08-11T08:40:37.374879','test-user','{}','2025-08-11 12:40:37');
INSERT INTO "conversations" VALUES(20,'test-flag-integration','user','Test user message for flag integration','2025-08-11T08:40:37.993106','test-user','{}','2025-08-11 12:40:37');
INSERT INTO "conversations" VALUES(21,'test-flag-integration','assistant','Test assistant response for flag integration','2025-08-11T08:40:38.007352','test-user','{}','2025-08-11 12:40:38');
INSERT INTO "conversations" VALUES(22,'test-e2e-conversation','user','I want to create a new feature for user authentication','2025-08-11T08:40:38.030909','test-user','{}','2025-08-11 12:40:38');
INSERT INTO "conversations" VALUES(23,'test-e2e-conversation','assistant','I''d be happy to help you plan the user authentication feature. Let''s start by understanding your requirements.','2025-08-11T08:40:38.042252','test-user','{}','2025-08-11 12:40:38');
CREATE TABLE memory_entries (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );
INSERT INTO "memory_entries" VALUES('test_memory_entry','This is a test memory entry','text','2025-08-11T08:40:37.342864','{}');
CREATE TABLE projects (
                name TEXT PRIMARY KEY,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                user_id TEXT DEFAULT 'anonymous',
                metadata TEXT DEFAULT '{}'
            );
INSERT INTO "projects" VALUES('ambers-project',NULL,'2025-08-04 13:35:18','2025-08-04T09:35:18.851639','app/memory/ambers-project.md','migration','{}');
INSERT INTO "projects" VALUES('demo',NULL,'2025-08-04 13:35:18','2025-08-04T09:35:18.884159','app/memory/demo.md','migration','{}');
INSERT INTO "projects" VALUES('project',NULL,'2025-08-04 13:35:18','2025-08-04T09:35:18.914029','app/memory/project.md','migration','{}');
INSERT INTO "projects" VALUES('test-dual-agent',NULL,'2025-08-04 13:35:18','2025-08-04T09:35:18.943791','app/memory/test-dual-agent.md','migration','{}');
INSERT INTO "projects" VALUES('test-document-project',NULL,'2025-08-11 12:40:37','2025-08-11T08:40:37.413114','app/memory/test-document-project.md','test-user','{}');
INSERT INTO "projects" VALUES('test-e2e-conversation',NULL,'2025-08-11 12:40:38','2025-08-11T08:40:38.078619','app/memory/test-e2e-conversation.md','test-user','{}');
CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                contributor TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                sections_updated TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active'
            );
CREATE INDEX idx_conversations_id ON conversations(conversation_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_projects_updated ON projects(updated_at);
CREATE INDEX idx_sessions_project ON sessions(project_name, user_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('conversations',23);
COMMIT;
