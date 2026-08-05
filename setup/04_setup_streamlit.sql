-- ============================================================
-- 04_setup_streamlit.sql
-- Create Streamlit app in Snowflake
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE CONVERSATIONAL_BI;
USE WAREHOUSE BI_ASSISTANT_WH;

-- Create a schema for the app
CREATE SCHEMA IF NOT EXISTS APP;

-- Create a stage to hold the Streamlit app code
CREATE STAGE IF NOT EXISTS APP.STREAMLIT_STAGE
    DIRECTORY = (ENABLE = TRUE);

-- Upload the app file to stage (run from SnowSQL or Snowsight):
-- PUT file://app/streamlit_app.py @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

-- Create the Streamlit app
CREATE OR REPLACE STREAMLIT APP.CONVERSATIONAL_BI_ASSISTANT
    ROOT_LOCATION = '@CONVERSATIONAL_BI.APP.STREAMLIT_STAGE'
    MAIN_FILE = 'streamlit_app.py'
    QUERY_WAREHOUSE = 'BI_ASSISTANT_WH'
    TITLE = 'DataForge';

-- Create the corrections table for "Learn from Mistakes" feature
CREATE TABLE IF NOT EXISTS APP.QUERY_CORRECTIONS (
    CORRECTION_ID INT AUTOINCREMENT PRIMARY KEY,
    QUESTION VARCHAR(1000),
    BAD_SQL VARCHAR(5000),
    CORRECTED_SQL VARCHAR(5000),
    REASON VARCHAR(500),
    BAD_VALUES VARCHAR(500),
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Grant access if needed
-- GRANT USAGE ON STREAMLIT APP.CONVERSATIONAL_BI_ASSISTANT TO ROLE <role_name>;
