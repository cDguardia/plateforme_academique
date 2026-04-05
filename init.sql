-- init.sql: créer la BD de base avec élèves, professeurs, admin
-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    role TEXT NOT NULL
);

-- Eleves
INSERT INTO users (first_name, last_name, role) VALUES
('Naruto','Uzumaki','Eleve'),
('Sasuke','Uchiha','Eleve'),
('Sakura','Haruno','Eleve'),
('Hinata','Hyuuga','Eleve'),
('Kiba','Inuzuka','Eleve'),
('Shino','Aburame','Eleve'),
('Shikamaru','Nara','Eleve'),
('Ino','Yamanaka','Eleve'),
('Chôji','Akimichi','Eleve'),
('Neji','Hyuuga','Eleve'),
('Rock','Lee','Eleve'),
('Tenten','Loubli','Eleve'),
('Gaara','No Sabaku','Eleve'),
('Temari','Nara','Eleve'),
('Kankuro','Lautre','Eleve');

-- Professeurs
INSERT INTO users (first_name, last_name, role) VALUES
('Kakashi','Hatake','Professeur'),
('Kurenaï','Sarutobi','Professeur'),
('Asuma','Sarutobi','Professeur'),
('Gaï','Maito','Professeur'),
('Jiraya','Senju','Professeur'),
('Orochimaru','Shiin','Professeur'),
('Itachi','Uchiha','Professeur');

-- Admin
INSERT INTO users (first_name, last_name, role) VALUES
('Tsunade','Senju','Admin');
