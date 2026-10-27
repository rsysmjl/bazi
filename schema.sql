-- ============================================================
-- 三盘命理智能分析平台 · MySQL 8.0 建库建表
-- 用法: mysql -u root -p < schema.sql
-- 建表后执行: python -m app.seed_prompts （灌入提示词模板与模块配置）
-- ============================================================

CREATE DATABASE IF NOT EXISTS mingpan DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mingpan;

-- 用户（MVP 仅匿名用户 id=1）
CREATE TABLE IF NOT EXISTS `user` (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nickname    VARCHAR(64)  NOT NULL DEFAULT '',
  status      TINYINT      NOT NULL DEFAULT 1 COMMENT '1=正常 0=禁用',
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户';

-- 出生信息
CREATE TABLE IF NOT EXISTS birth_info (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id         INT UNSIGNED NOT NULL DEFAULT 1,
  subject_name    VARCHAR(64)  NOT NULL DEFAULT '本人',
  birth_year      SMALLINT     NOT NULL,
  birth_month     TINYINT      NOT NULL,
  birth_day       TINYINT      NOT NULL,
  birth_hour      TINYINT      NOT NULL,
  birth_minute    TINYINT      NOT NULL,
  gender          VARCHAR(10)  NOT NULL COMMENT 'male/female',
  birth_place     VARCHAR(128) NOT NULL DEFAULT '',
  longitude       DECIMAL(9,6) NULL COMMENT '东经，用于真太阳时',
  timezone        VARCHAR(32)  NOT NULL DEFAULT 'Asia/Shanghai',
  hour_known      TINYINT      NOT NULL DEFAULT 1 COMMENT '时辰是否准确',
  solar_time_note VARCHAR(255) NOT NULL DEFAULT '',
  is_default      TINYINT      NOT NULL DEFAULT 0,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='出生信息（含真太阳时校正说明）';

-- 问事（奇门用）
CREATE TABLE IF NOT EXISTS divination_query (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id         INT UNSIGNED NOT NULL DEFAULT 1,
  chart_record_id INT UNSIGNED NULL,
  question_type   VARCHAR(32)  NOT NULL DEFAULT 'general',
  ask_year        SMALLINT     NOT NULL,
  ask_month       TINYINT      NOT NULL,
  ask_day         TINYINT      NOT NULL,
  ask_hour        TINYINT      NOT NULL,
  ask_minute      TINYINT      NOT NULL,
  ask_place       VARCHAR(128) NOT NULL DEFAULT '',
  longitude       DECIMAL(9,6) NULL,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_record (chart_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='奇门问事';

-- 排盘记录（三盘结构化结果 JSON）
CREATE TABLE IF NOT EXISTS chart_record (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id         INT UNSIGNED NOT NULL DEFAULT 1,
  birth_info_id   INT UNSIGNED NOT NULL,
  chart_no        VARCHAR(32)  NOT NULL,
  provider_bazi   VARCHAR(16)  NOT NULL DEFAULT 'local',
  provider_ziwei  VARCHAR(16)  NOT NULL DEFAULT 'local',
  provider_qimen  VARCHAR(16)  NOT NULL DEFAULT 'local',
  bazi_pillars    JSON NULL,
  bazi_day_master VARCHAR(4)   NULL,
  bazi_five_elems JSON NULL,
  bazi_ten_gods   JSON NULL,
  bazi_dayun      JSON NULL,
  bazi_liunian    JSON NULL,
  ziwei_palaces   JSON NULL,
  ziwei_soul      VARCHAR(8)   NULL,
  ziwei_body      VARCHAR(8)   NULL,
  ziwei_five_class VARCHAR(16) NULL,
  qimen_dun       VARCHAR(8)   NULL COMMENT '阳遁/阴遁',
  qimen_ju        TINYINT      NULL,
  qimen_zhi_fu    VARCHAR(8)   NULL,
  qimen_zhi_shi   VARCHAR(8)   NULL,
  qimen_palaces   JSON NULL,
  warnings        JSON NULL,
  status          TINYINT      NOT NULL DEFAULT 1,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_chart_no (chart_no),
  KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='排盘记录';

-- 解读报告
CREATE TABLE IF NOT EXISTS interpret_report (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  report_no       VARCHAR(32)  NOT NULL,
  user_id         INT UNSIGNED NOT NULL DEFAULT 1,
  chart_record_id INT UNSIGNED NOT NULL,
  mode            VARCHAR(16)  NOT NULL DEFAULT 'overview' COMMENT 'overview/focus',
  question        VARCHAR(500) NULL,
  overview        MEDIUMTEXT   NULL,
  focus_content   MEDIUMTEXT   NULL,
  confidence_note VARCHAR(255) NOT NULL DEFAULT '',
  disclaimer      VARCHAR(255) NOT NULL DEFAULT '',
  llm_model       VARCHAR(64)  NULL,
  token_input     INT          NOT NULL DEFAULT 0,
  token_output    INT          NOT NULL DEFAULT 0,
  status          TINYINT      NOT NULL DEFAULT 1,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_report_no (report_no),
  KEY idx_record (chart_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='解读报告';

-- 报告分模块小节
CREATE TABLE IF NOT EXISTS report_module (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  report_id   INT UNSIGNED NOT NULL,
  module_key  VARCHAR(32)  NOT NULL,
  module_name VARCHAR(32)  NOT NULL,
  content_md  MEDIUMTEXT   NULL,
  sort_order  INT          NOT NULL DEFAULT 0,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_report (report_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告分模块正文';

-- LLM 调用日志（成本与可观测）
CREATE TABLE IF NOT EXISTS llm_call_log (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id       INT UNSIGNED NOT NULL DEFAULT 1,
  report_id     INT UNSIGNED NULL,
  scene         VARCHAR(64)  NOT NULL DEFAULT '',
  provider      VARCHAR(128) NULL,
  model         VARCHAR(64)  NULL,
  request_msgs  TEXT         NULL,
  response_text MEDIUMTEXT   NULL,
  token_input   INT          NOT NULL DEFAULT 0,
  token_output  INT          NOT NULL DEFAULT 0,
  latency_ms    INT          NOT NULL DEFAULT 0,
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '1=成功 0=失败',
  error_msg     VARCHAR(500) NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_report (report_id),
  KEY idx_scene (scene)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM 调用日志';

-- 提示词模板（外置可热更新）
CREATE TABLE IF NOT EXISTS prompt_template (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tpl_key    VARCHAR(64)  NOT NULL,
  tpl_name   VARCHAR(128) NOT NULL DEFAULT '',
  version    VARCHAR(32)  NOT NULL DEFAULT 'v1.0.0',
  content    TEXT         NOT NULL,
  is_active  TINYINT      NOT NULL DEFAULT 1,
  remark     VARCHAR(255) NOT NULL DEFAULT '',
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_key_version (tpl_key, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提示词模板';

-- 解读模块配置
CREATE TABLE IF NOT EXISTS module_config (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  module_key  VARCHAR(32)  NOT NULL,
  module_name VARCHAR(32)  NOT NULL,
  focus_desc  TEXT         NULL,
  is_enabled  TINYINT      NOT NULL DEFAULT 1,
  is_free     TINYINT      NOT NULL DEFAULT 1,
  sort_order  INT          NOT NULL DEFAULT 0,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_module (module_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='解读模块配置';
