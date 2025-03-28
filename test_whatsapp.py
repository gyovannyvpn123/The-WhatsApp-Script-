import json
import logging
import time
from whatsapp_service import WhatsAppMessenger
from threading import Event

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_whatsapp_message():
    """Test sending a WhatsApp message using the WhatsAppMessenger class."""
    try:
        # Load credentials from file
        with open('attached_assets/creds.json', 'r') as f:
            credentials = json.load(f)
        
        # Target phone number (modify this with the number you want to test)
        target_number = input("Introduceți numărul de telefon pentru test (format: +123456789): ")
        
        # Message text
        message_text = input("Introduceți textul mesajului de test: ")
        
        # Create stop event (for stopping the messaging process)
        stop_event = Event()
        
        # Create messenger instance
        messenger = WhatsAppMessenger(credentials)
        
        # Initialize WebDriver
        logger.info("Inițializare WebDriver...")
        if not messenger.initialize_driver():
            logger.error("Nu s-a putut inițializa WebDriver-ul!")
            return False
        
        # Login to WhatsApp
        logger.info("Autentificare în WhatsApp Web...")
        if not messenger.login_to_whatsapp():
            logger.error("Autentificare eșuată! Asigurați-vă că fișierul creds.json este valid.")
            messenger.driver.quit()
            return False
        
        # Send a single message
        logger.info(f"Trimitere mesaj de test către {target_number}...")
        success = messenger.send_message(target_number, message_text)
        
        if success:
            logger.info("✓ Mesaj trimis cu succes!")
        else:
            logger.error("✗ Eroare la trimiterea mesajului!")
        
        # Take screenshot for verification
        try:
            messenger.driver.save_screenshot("whatsapp_test_screenshot.png")
            logger.info("Captură de ecran salvată în 'whatsapp_test_screenshot.png'")
        except Exception as e:
            logger.error(f"Nu s-a putut salva captura de ecran: {str(e)}")
        
        # Cleanup
        messenger.driver.quit()
        logger.info("Test finalizat.")
        
        return success
    
    except Exception as e:
        logger.error(f"Eroare în timpul testului: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== TEST FUNCȚIONALITATE WHATSAPP ===")
    print("Acest script va testa trimiterea unui mesaj real prin WhatsApp.")
    
    input("Apăsați ENTER pentru a continua...")
    
    result = test_whatsapp_message()
    
    if result:
        print("\n✓ Testul a fost finalizat cu succes! Mesajul a fost trimis.")
    else:
        print("\n✗ Testul a eșuat! Verificați log-urile pentru detalii.")