import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "." 

st.set_page_config(page_title="Football Quiz PRO", layout="centered", page_icon="⚽")

# --- CSS (Wygląd) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .score-board {
        display: flex; justify-content: space-between; 
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 24px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
    }
    .player-box {
        text-align: center; padding: 10px; border-radius: 8px; width: 45%;
    }
    .p1-box { background-color: #1b5e20; } /* Zielony dla P1 */
    .p2-box { background-color: #0d47a1; } /* Niebieski dla P2 */
    
    .status-msg {
        text-align: center; font-size: 18px; font-weight: bold; padding: 10px;
        color: #ffca28;
    }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN SERWERA (Wspólny dla wszystkich) ---
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby"
        self.current_team = None
        self.current_image = None
        self.winner_last_round = None
        self.image_pool = []
        self.round_id = 0 # Unikalny ID rundy do odświeżania inputów

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# --- LOKALNY STAN (Tylko dla Twojej przeglądarki) ---
# To naprawia problem nr 2: Przeglądarka wie, kim jest.
if 'my_role' not in st.session_state:
    st.session_state.my_role = None  # Może być: "P1", "P2" lub None (Obserwator)

# --- FUNKCJE LOGIKI ---
def load_images_once():
    if server.image_pool: return
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return
    images = []
    for root, dirs, files in os.walk(FOLDER_Z_KOSZULKAMI):
        for file in files:
            if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                team = os.path.basename(root).replace("_", " ")
                if team == "." or team == FOLDER_Z_KOSZULKAMI: continue
                full_path = os.path.join(root, file)
                images.append((team, full_path))
    server.image_pool = images
    if server.image_pool:
        new_round_logic()

def new_round_logic():
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    server.winner_last_round = None
    server.round_id += 1 # Zmiana ID wymusi wyczyszczenie pola wyboru u graczy

def reset_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    new_round_logic()

# Ładowanie zdjęć na starcie
load_images_once()

# --- TYTUŁ ---
st.title("🌍 Football Quiz: ONLINE")

# --- 1. LOBBY (Wybór kim jesteś) ---
if server.status == "lobby":
    st.info("👋 Witaj w Lobby! Wybierz miejsce.")
    
    col1, col2 = st.columns(2)
    
    # KARTA GRACZA 1
    with col1:
        st.markdown("<div class='player-box p1-box'>GRACZ 1 (Gospodarz)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"Zajęte przez: {server.p1_name}")
            # Jeśli to JA jestem P1, pokazuję to
            if st.session_state.my_role == "P1":
                st.caption("(To Ty)")
        else:
            nick1 = st.text_input("Twój Nick:", key="nick1")
            if st.button("Dołącz jako P1"):
                if nick1:
                    server.p1_name = nick1
                    st.session_state.my_role = "P1" # <--- PRZYPISANIE ROLI
                    st.rerun()

    # KARTA GRACZA 2
    with col2:
        st.markdown("<div class='player-box p2-box'>GRACZ 2 (Gość)</div>", unsafe_allow_html=True)
        if server.p2_name:
            st.success(f"Zajęte przez: {server.p2_name}")
            if st.session_state.my_role == "P2":
                st.caption("(To Ty)")
        else:
            nick2 = st.text_input("Twój Nick:", key="nick2")
            if st.button("Dołącz jako P2"):
                if nick2:
                    server.p2_name = nick2
                    st.session_state.my_role = "P2" # <--- PRZYPISANIE ROLI
                    st.rerun()

    st.divider()
    
    # Przycisk startu widzi tylko P1 (Gospodarz)
    if server.p1_name and server.p2_name:
        if st.session_state.my_role == "P1":
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                server.status = "playing"
                st.rerun()
        else:
            st.warning("Czekanie aż Gospodarz (P1) rozpocznie mecz...")
            time.sleep(2) # Odświeżanie dla P2 w lobby
            st.rerun()
    else:
        # Odświeżanie lobby, żeby widzieć jak ktoś dołączy
        time.sleep(2)
        st.rerun()

# --- 2. ROZGRYWKA ---
elif server.status == "playing":
    
    # TABLICA WYNIKÓW
    st.markdown(f"""
    <div class="score-board">
        <div style="color: #4CAF50">{server.p1_name}: {server.p1_score}</div>
        <div style="font-size: 16px; align-self: center;">VS</div>
        <div style="color: #2196F3">{server.p2_name}: {server.p2_score}</div>
    </div>
    """, unsafe_allow_html=True)

    # INFORMACJA O ZWYCIĘZCY RUNDY
    if server.winner_last_round:
        st.markdown(f"<div class='status-msg'>🏆 RUNDĘ WYGRYWA: {server.winner_last_round}!</div>", unsafe_allow_html=True)
        
        # Tylko P1 może przejść dalej (żeby nie było chaosu), albo automat
        if st.session_state.my_role == "P1":
            if st.button("Następna Runda ➡️", type="primary"):
                new_round_logic()
                st.rerun()
        else:
            st.info("Czekanie na rozpoczęcie kolejnej rundy...")
            time.sleep(1)
            st.rerun()
        st.stop() # Zatrzymaj renderowanie reszty

    # WYŚWIETLANIE ZDJĘCIA
    if server.current_image:
        try:
            img = Image.open(server.current_image)
            st.image(img, use_container_width=True)
        except:
            st.error("Błąd zdjęcia")
            new_round_logic()
            st.rerun()

    # FORMULARZ ODPOWIEDZI
    all_teams = sorted(list(set([x[0] for x in server.image_pool])))
    
    # Klucz zawiera round_id, dzięki temu selectbox czyści się co rundę
    user_guess = st.selectbox("Wybierz drużynę:", [""] + all_teams, key=f"g_{server.round_id}")

    # --- OBSŁUGA PRZYCISKÓW WG ROLI ---
    # To jest serce naprawy problemu nr 2!
    
    if st.session_state.my_role == "P1":
        # Widzi tylko przycisk P1
        if st.button(f"Zgłaszam to! ({server.p1_name})", type="primary", use_container_width=True):
            if user_guess == server.current_team:
                server.p1_score += 1
                server.winner_last_round = server.p1_name
                st.rerun()
            else:
                st.toast("❌ Źle! Strzelaj dalej!", icon="⚠️")

    elif st.session_state.my_role == "P2":
        # Widzi tylko przycisk P2
        if st.button(f"Zgłaszam to! ({server.p2_name})", type="primary", use_container_width=True):
            if user_guess == server.current_team:
                server.p2_score += 1
                server.winner_last_round = server.p2_name
                st.rerun()
            else:
                st.toast("❌ Źle! Strzelaj dalej!", icon="⚠️")
                
    else:
        # Obserwator
        st.info("Jesteś obserwatorem. Oglądaj mecz!")

    # --- AUTO-ODŚWIEŻANIE (Fix problemu nr 1) ---
    # Kod poniżej sprawia, że strona sama się odświeża co 1.5 sekundy
    # dzięki czemu widzisz, gdy przeciwnik zdobędzie punkt.
    time.sleep(1.5)
    st.rerun()

# Przycisk resetu dostępny zawsze w pasku bocznym
if st.sidebar.button("HARD RESET SERWERA ⚠️"):
    reset_game()
    st.session_state.my_role = None
    st.rerun()
