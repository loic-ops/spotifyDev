mysqldump: [Warning] Using a password on the command line interface can be insecure.
mysqldump: Error: 'Access denied; you need (at least one of) the PROCESS privilege(s) for this operation' when trying to dump tablespaces
-- MySQL dump 10.13  Distrib 8.0.45, for Linux (aarch64)
--
-- Host: localhost    Database: karaoke_db
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `admins`
--

DROP TABLE IF EXISTS `admins`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `admins` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `admins`
--

LOCK TABLES `admins` WRITE;
/*!40000 ALTER TABLE `admins` DISABLE KEYS */;
INSERT INTO `admins` VALUES (1,'admin','$2b$12$h6OR3Yew1YXvLOby3ydD9O7l1PVjtHF.K6wrkcsZJlfsq4GDEBkjW','2026-04-07 09:48:40');
/*!40000 ALTER TABLE `admins` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `processing`
--

DROP TABLE IF EXISTS `processing`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `processing` (
  `id` int NOT NULL AUTO_INCREMENT,
  `song_id` varchar(36) DEFAULT NULL,
  `method` varchar(50) DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `song_id` (`song_id`),
  CONSTRAINT `processing_ibfk_1` FOREIGN KEY (`song_id`) REFERENCES `songs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `processing`
--

LOCK TABLES `processing` WRITE;
/*!40000 ALTER TABLE `processing` DISABLE KEYS */;
/*!40000 ALTER TABLE `processing` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `songs`
--

DROP TABLE IF EXISTS `songs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `songs` (
  `id` varchar(36) NOT NULL,
  `title` varchar(255) NOT NULL,
  `original_file` varchar(255) NOT NULL,
  `instrumental_file` varchar(255) DEFAULT NULL,
  `vocals_file` varchar(255) DEFAULT NULL,
  `lyrics_file` text,
  `created_at` datetime DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `songs`
--

LOCK TABLES `songs` WRITE;
/*!40000 ALTER TABLE `songs` DISABLE KEYS */;
INSERT INTO `songs` VALUES ('053108c4-bc4a-45d6-8211-e2972270e12d','Hillsong (Cover by Lloyiso)','053108c4-bc4a-45d6-8211-e2972270e12d.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 13:50:04','separated'),('15b73749-f8f5-4a7c-84db-7aa82d2fd5d4','ART','15b73749-f8f5-4a7c-84db-7aa82d2fd5d4.mp3',NULL,NULL,'lyrics.lrc','2026-04-07 15:24:42','youtube'),('37ef637d-d040-4dfc-91ac-52f5ed1bd2d3','Laugh Now Cry Later  ft. Lil Durk','37ef637d-d040-4dfc-91ac-52f5ed1bd2d3.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 15:15:41','separated'),('3866d909-7035-40a8-aadf-6ea34eb36b38','J\'me tire (Paroles)','3866d909-7035-40a8-aadf-6ea34eb36b38.mp3',NULL,NULL,'lyrics.lrc','2026-04-07 17:48:11','youtube'),('4ccd22eb-3de9-4fbc-9264-4b0be9986e27','Ghost','4ccd22eb-3de9-4fbc-9264-4b0be9986e27.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 10:28:13','separated'),('54896f11-1d5a-496e-9689-d413c66b7536','WORSHIP','54896f11-1d5a-496e-9689-d413c66b7536.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 10:44:15','separated'),('6b99e120-b637-44fd-9996-b3d4eb79dfa0','SOMÉ','6b99e120-b637-44fd-9996-b3d4eb79dfa0.mp3',NULL,NULL,NULL,'2026-04-07 19:18:35','youtube'),('7323b583-4adb-4d65-93ba-3b742d6a6baa','SZA_-_Nobody_Gets_Me_Lyric_Video_-_SZAVEVO','7323b583-4adb-4d65-93ba-3b742d6a6baa.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 19:24:42','separated'),('aeb2d35e-3d46-4958-a33e-3c1e3fe087b6','What You Saying -','aeb2d35e-3d46-4958-a33e-3c1e3fe087b6.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 12:15:51','separated'),('c3f7dc88-2c5e-403a-902a-d6330b47f6db','Hello','c3f7dc88-2c5e-403a-902a-d6330b47f6db.mp3',NULL,NULL,NULL,'2026-04-07 18:59:46','youtube'),('ded337c4-14dd-4c4e-a805-18e6849bf595','Dis_pas_un_mot_Clip_officiel','ded337c4-14dd-4c4e-a805-18e6849bf595.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 11:06:26','separated'),('eb0276f5-5bc7-4ab8-b2d9-82d26b851ea8','Scary','eb0276f5-5bc7-4ab8-b2d9-82d26b851ea8.mp3',NULL,NULL,'lyrics.lrc','2026-04-07 15:16:38','youtube'),('f2147a0d-043f-4e4d-9224-edcf70492733','Believe  [4K Remaster]','f2147a0d-043f-4e4d-9224-edcf70492733.mp3','instrumental.wav','vocals.wav','lyrics.lrc','2026-04-07 14:55:07','separated');
/*!40000 ALTER TABLE `songs` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-08 17:17:19
