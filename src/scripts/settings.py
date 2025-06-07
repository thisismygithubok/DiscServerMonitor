import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "AdminIDs": [],
    "AllowedRoles": []
}

def check_settings_file():
    config_path = Path("/config/settings.json")
    logger.info(f"Checking for settings file...")
    
    try:
        if not config_path.parent.exists():
            logger.debug("Creating config folder...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
        if not config_path.exists():
            logger.debug("Creating new settings.json with default values...")
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4)
        else:
            with open(config_path, 'r') as f:
                current_settings = json.load(f)
                logger.debug(f"Settings file already exists, loading...")
            
            updated = False
            for key, value in DEFAULT_SETTINGS.items():
                if key not in current_settings:
                    current_settings[key] = value
                    updated = True
            
            if updated:
                logger.info("Updating settings.json user-defined values...")
                with open(config_path, 'w') as f:
                    json.dump(current_settings, f, indent=4)
            else:
                logger.info("Settings file is up-to-date")
                
    except Exception as e:
        logger.error(f"Error managing settings file: {e}")
        raise

if __name__ == "__main__":
    check_settings_file()