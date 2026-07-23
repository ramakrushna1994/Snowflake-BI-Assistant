-- ============================================================
-- 01_create_database.sql
-- Creates database, schemas, and warehouse for Conversational BI
-- ============================================================

USE ROLE ACCOUNTADMIN;

-- Create warehouse
CREATE WAREHOUSE IF NOT EXISTS BI_ASSISTANT_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- Create database
CREATE DATABASE IF NOT EXISTS CONVERSATIONAL_BI;

USE DATABASE CONVERSATIONAL_BI;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS SALES;
CREATE SCHEMA IF NOT EXISTS HR;

-- Grant usage
GRANT USAGE ON WAREHOUSE BI_ASSISTANT_WH TO ROLE ACCOUNTADMIN;
