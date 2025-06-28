-- Steam Games Database Schema
-- Created for Steam game data crawling project

-- Create database (optional - can be created separately)
-- CREATE DATABASE IF NOT EXISTS steam_games CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE steam_games;

-- 1. Games (메인 테이블)
CREATE TABLE IF NOT EXISTS games (
    app_id INT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    detailed_description TEXT,
    release_date DATE,
    developer VARCHAR(255),
    publisher VARCHAR(255),
    updated_at DATETIME,
    header_image_url VARCHAR(500),
    system_requirements_minimum TEXT,
    system_requirements_recommended TEXT,
    metacritic_score INT,

    -- 인덱스
    INDEX idx_title (title),
    INDEX idx_developer (developer),
    INDEX idx_release_date (release_date),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. Game Tags (태그 - 다대다 관계)
CREATE TABLE IF NOT EXISTS game_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tag_order TINYINT UNSIGNED DEFAULT 1,
    tag_order INT,
>>>>>>> feature/integrate-latest-with-db
    
    FOREIGN KEY (app_id) REFERENCES games(app_id) ON DELETE CASCADE,
    INDEX idx_app_id (app_id),
    INDEX idx_tag_name (tag_name),
    INDEX idx_tag_order (tag_order),
    UNIQUE KEY unique_app_tag (app_id, tag_name)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 3. Game Genres (장르 - 다대다 관계)
CREATE TABLE IF NOT EXISTS game_genres (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id INT NOT NULL,
    genre_name VARCHAR(50) NOT NULL,
    
    FOREIGN KEY (app_id) REFERENCES games(app_id) ON DELETE CASCADE,
    INDEX idx_app_id (app_id),
    INDEX idx_genre_name (genre_name),
    UNIQUE KEY unique_app_genre (app_id, genre_name)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 4. Game Pricing (가격 정보)
CREATE TABLE IF NOT EXISTS game_pricing (
    app_id INT PRIMARY KEY,
    current_price VARCHAR(50),
    original_price VARCHAR(50),
    discount_percent INT,
    is_free TINYINT(1),
    updated_at DATETIME,
    
    FOREIGN KEY (app_id) REFERENCES games(app_id) ON DELETE CASCADE,
    INDEX idx_is_free (is_free),
    INDEX idx_discount_percent (discount_percent),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 5. Game Reviews (리뷰 정보)
CREATE TABLE IF NOT EXISTS game_reviews (
    app_id INT PRIMARY KEY,
    recent_reviews VARCHAR(50),
    all_reviews VARCHAR(50),
    recent_review_count INT,
    total_review_count INT,
    recent_positive_percent INT,
    total_positive_percent INT,
    updated_at DATETIME,
    
    FOREIGN KEY (app_id) REFERENCES games(app_id) ON DELETE CASCADE,
    INDEX idx_recent_reviews (recent_reviews),
    INDEX idx_all_reviews (all_reviews),
    INDEX idx_total_positive_percent (total_positive_percent),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 자주 사용하는 복합 인덱스 추가
ALTER TABLE game_tags ADD INDEX idx_tag_name_app_id (tag_name, app_id);
ALTER TABLE game_genres ADD INDEX idx_genre_name_app_id (genre_name, app_id);

-- 통계용 뷰 생성 (선택사항)
CREATE OR REPLACE VIEW game_stats AS
SELECT 
    g.app_id,
    g.title,
    g.developer,
    g.release_date,
    gp.current_price,
    gp.is_free,
    gr.total_positive_percent,
    gr.total_review_count,
    GROUP_CONCAT(DISTINCT gt.tag_name ORDER BY gt.tag_order SEPARATOR ', ') as tags,
    GROUP_CONCAT(DISTINCT gg.genre_name SEPARATOR ', ') as genres
FROM games g
LEFT JOIN game_pricing gp ON g.app_id = gp.app_id
LEFT JOIN game_reviews gr ON g.app_id = gr.app_id
LEFT JOIN game_tags gt ON g.app_id = gt.app_id
LEFT JOIN game_genres gg ON g.app_id = gg.app_id
GROUP BY g.app_id; 