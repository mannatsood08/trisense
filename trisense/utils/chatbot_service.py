import requests
import json
import re

class ChatbotService:
    def __init__(self, ollama_url="http://localhost:11434/api/generate", model="llama3"):
        self.ollama_url = ollama_url
        self.model = model
        
        # Core safety rules (Regex based for speed and reliability)
        self.safety_rules = [
            (r"(help|emergency|save me|sos|falling|fell)", 
             "🚨 EMERGENCY DETECTED: I am notifying the emergency manager. Please stay calm. Should I call a doctor or an ambulance?"),
            (r"(medicine|pill|tablet|take my med)", 
             "HEALTH REMINDER: You can view your scheduled medicines in the 'My Medicines' panel. It is important to follow the prescribed times."),
            (r"(pain|hurt|sick|blood|doctor|ambulance)", 
             "SAFETY ADVICE: If you are in pain or feel unwell, please use the 'Call Doctor' button immediately. I can also try to message them for you."),
            (r"(drink|water|hydrat)", 
             "CARE TIP: Staying hydrated is key to wellbeing. Please drink a glass of water if you haven't recently.")
        ]

    def get_response(self, user_input, context):
        """
        user_input: str
        context: dict containing {username, role, system_state, prescriptions}
        """
        user_input_lower = user_input.lower()
        
        # 1. Rule-Based Priority (Override)
        for pattern, response in self.safety_rules:
            if re.search(pattern, user_input_lower):
                print(f"[ChatbotService] Rule Matched: {pattern}")
                # Inject personal context if possible
                if "medicine" in pattern:
                    meds = context.get('prescriptions', [])
                    if meds:
                         med_names = ", ".join([p['medicine'] for p in meds])
                         response += f" Your current list includes: {med_names}."
                return response

        # 2. LLM Fallback (Ollama)
        print(f"[ChatbotService] No rule matched. Falling back to LLM ({self.model})...")
        return self._get_llm_response(user_input, context)

    def _get_llm_response(self, user_input, context):
        system_prompt = (
            "You are a compassionate wellbeing assistant for the TriSense safety system. "
            "Your goal is to provide comfort, health tips, and light conversation. "
            "CRITICAL: Do not provide medical diagnosis or specific prescription changes. "
            "Keep responses short (under 2-3 sentences). "
            f"Current System State: {context.get('system_state', 'NORMAL')}. "
            f"User: {context.get('username', 'User')}."
        )

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\nUser: {user_input}\nAssistant:",
            "stream": False
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "I'm here for you, but I'm having trouble thinking clearly right now.")
            else:
                return "Ollama is responding with an error. I am still monitoring your safety regardless."
        except Exception as e:
            print(f"[ChatbotService] Ollama Error: {e}")
            return "I am here to help, though my conversational brain (Ollama) is currently offline. Your safety monitoring is still fully active."

chatbot_service = ChatbotService()
