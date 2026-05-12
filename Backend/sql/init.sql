CREATE DATABASE IF NOT EXISTS dataprocess_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE dataprocess_agent;

CREATE TABLE IF NOT EXISTS dataset_task (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_name       VARCHAR(128)  NOT NULL,
    task_description TEXT,
    task_status     VARCHAR(32)   NOT NULL DEFAULT 'INIT',
    current_step    VARCHAR(64),
    progress        INT           NOT NULL DEFAULT 0,
    need_user_confirm TINYINT(1)  NOT NULL DEFAULT 0,
    confirm_payload JSON,
    plan_observations JSON,
    error_message   TEXT,
    parent_task_id  BIGINT,
    round_index     INT           NOT NULL DEFAULT 0,
    refinement_action TEXT,
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dataset_file (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id      BIGINT        NOT NULL,
    file_name    VARCHAR(255)  NOT NULL,
    file_type    VARCHAR(32),
    file_role    VARCHAR(32)   NOT NULL DEFAULT 'raw',
    storage_type VARCHAR(16)   NOT NULL DEFAULT 'local',
    file_path    VARCHAR(512),
    file_url     VARCHAR(1024),
    file_size    BIGINT,
    INDEX idx_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS skill_execution_log (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id          BIGINT        NOT NULL,
    skill_name       VARCHAR(128)  NOT NULL,
    execution_order  INT           NOT NULL DEFAULT 0,
    execution_status VARCHAR(32)   NOT NULL DEFAULT 'success',
    input_summary    TEXT,
    output_summary   TEXT,
    execution_time_ms BIGINT,
    error_message    TEXT,
    INDEX idx_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS analysis_report (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id      BIGINT  NOT NULL,
    report_json  JSON,
    summary_text TEXT,
    create_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chat_message (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id     BIGINT       NOT NULL,
    role        VARCHAR(16)  NOT NULL,
    content     MEDIUMTEXT,
    create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
