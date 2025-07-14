import asyncio
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

from database.pgvector import PGVector, PGVectorConfig
from api.api import app

# Load environment variables from project root
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('philparse.log')
    ]
)

logger = logging.getLogger(__name__)

if os.path.exists(env_path):
    logger.info(f"Loaded .env file from: {env_path}")
else:
    logger.warning(f".env file not found at: {env_path}, relying on system environment variables.")


def get_server_config() -> dict:
   # In Docker, we want to use port 8000 internally, regardless of external mapping
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))  # Always use 8000 internally for Docker
    
    config = {
        'host': host,
        'port': port,
        'log_level': os.getenv('LOG_LEVEL', 'info'),
        'reload': os.getenv('RELOAD', 'false').lower() == 'true',
        'workers': int(os.getenv('WORKERS', '1')),
    }
    
    logger.info(f"Server config: {config}")
    return config


def validate_environment():
    """
    Validate that required environment variables are set.
    """
    required_vars = [
        'POSTGRES_HOST',
        'POSTGRES_PORT', 
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file or set these environment variables")
        sys.exit(1)


async def check_database_connection():
    # Database connection is now handled by the FastAPI lifespan handler
    # This function is kept for potential future use but is no longer required
    logger.info("Database connection will be tested during app startup")


def main():
    try:
        logger.info("PhilParse Backend Starting...")
        
        # Log current working directory and environment
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Python path: {sys.path}")
        # logger.info(f"Environment variables: PORT={os.getenv('PORT')}, APP_PORT={os.getenv('APP_PORT')}")
        # Validate environment
        validate_environment()
        
        # Test database connection
        asyncio.run(check_database_connection())
        
        # Get server configuration
        server_config = get_server_config()
        
        logger.info(f"Starting server on {server_config['host']}:{server_config['port']}")
        logger.info(f"Frontend will be served at http://{server_config['host']}:{server_config['port']}/")
        logger.info(f"API endpoints available at http://{server_config['host']}:{server_config['port']}/api/")
        logger.info(f"Health check available at http://{server_config['host']}:{server_config['port']}/health")
        
        # Start the FastAPI server - fix module path for Docker
        # Import the app directly to ensure it's available
        uvicorn.run(
            app,  # Pass the app object directly instead of module string
            **server_config
        )
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()