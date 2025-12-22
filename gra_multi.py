import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "." 

st.set_page_config(page_title="Football Quiz ULTIMATE", layout="centered", page_icon="⚽")

# --- CSS (Wygląd) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    
    /* Tablica wyników */
    .score-board {
        display: flex; justify-content: space-between; 
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 24px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
    }
    
    /* Karty graczy */
    .player-box {
        text-align: center; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold;
    }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    
    /* Komunikat o turze */
    .turn-alert {
        text-align: center; color: #ffca28; font-weight: bold; margin-bottom: 10px;
    }
    
    /* Ekran zwycięstwa rundy */
    .winner-banner {
        background-color: #ffd700; color: black; padding: 20px;
        text-align: center; border-radius: 10px; font-size: 24px; font-weight: bold;
        margin-bottom: 20px; animation: fadeIn 0.5s;
    }
    .correct-answer {
        font-size: 30px; color: #4CAF50; text-align: center; font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN SERWERA ---
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby"      # lobby, playing, round_over
        
        # Dane rundy
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        
        # Logika tur i blokad
        self.p1_locked = False     # Czy P1 jest zablokowany (bo spudłował)
        self.p2_locked = False     # Czy P2 jest zablokowany
        
        # Koniec rundy
        self.winner_last_round = None # Kto wygrał ("P1", "P2" lub "SKIP")
        self.last_correct_answer = "" # Tekst odpowiedzi do wyświetlenia
        self.next_starter = "P1"      # Kto ma prawo kliknąć "Dalej" (P1 lub P2)

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# --- LOKALNY STAN (Rola w przeglądarce) ---
if 'my_role' not in st.session_state:
    st.session_state.my_role = None

# --- FUNKCJE LOGIKI ---

def get_available_leagues():
    """Zwraca listę dostępnych lig (nazw folderów)"""
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return []
    leagues = []
    for item in os.listdir(FOLDER_Z_KOSZULKAMI):
        if os.path.isdir(os.path.join(FOLDER_Z_KOSZULKAMI, item)) and not item.startswith("."):
            leagues.append(item.replace("_", " "))
    return sorted(leagues)

def load_images_filtered(selected_leagues):
    """Ładuje zdjęcia tylko z wybranych lig"""
    server.image_pool = []
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return
    
    for root, dirs, files in os.walk(FOLDER_Z_KOSZULKAMI):
        # Sprawdzamy czy ten folder należy do wybranej ligi
        # Ścieżka root np: ./MEGA/Anglia_Premier/Arsenal
        folder_parts = root.split(os.sep)
        
        # Szukamy, czy w ścieżce jest którakolwiek z wybranych lig
        match = False
        for part in folder_parts:
            if part.replace("_", " ") in selected_leagues:
                match = True
                break
        
        if match:
            for file in files:
                if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                    team = os.path.basename(root).replace("_", " ")
                    if team == "." or team == FOLDER_Z_KOSZULKAMI: continue
                    full_path = os.path.join(root, file)
                    server.image_pool.append((team, full_path))

def start_new_round():
    """Losuje nowe zdjęcie i resetuje blokady"""
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    
    # Reset blokad - nowa runda, obaj mogą strzelać
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1

def handle_wrong_guess(player_role):
    """Blokuje gracza, który spudłował i odblokowuje przeciwnika"""
    if player_role == "P1":
        server.p1_locked = True  # P1 zablokowany
        server.p2_locked = False # P2 dostaje szansę
    else:
        server.p2_locked = True  # P2 zablokowany
        server.p1_locked = False # P1 dostaje szansę

def reset_full_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    server.p1_locked = False
    server.p2_locked = False
    server.next_starter = "P1"

# --- TYTUŁ ---
st.title("⚽ Football Quiz: TURNIEJ")

# ==============================================================================
# 1. LOBBY
# ==============================================================================
if server.status == "lobby":
    st.info("👋 Witaj w Lobby! Wybierz miejsce.")
    
    col1, col2 = st.columns(2)
    
    # KARTA GRACZA 1
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"Gotowy: {server.p1_name}")
            if st.session_state.my_role == "P1": st.caption("(To Ty)")
        else:
            nick1 = st.text_input("Nick P1", key="n1")
            if st.button("Zajmij P1"):
                if nick1:
                    server.p1_name = nick1
                    st.session_state.my_role = "P1"
                    st.rerun()

    # KARTA GRACZA 2
    with col2:
        st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
        if server.p2_name:
            st.success(f"Gotowy: {server.p2_name}")
            if st.session_state.my_role == "P2": st.caption("(To Ty)")
        else:
            nick2 = st.text_input("Nick P2", key="n2")
            if st.button("Zajmij P2"):
                if nick2:
                    server.p2_name = nick2
                    st.session_state.my_role = "P2"
                    st.rerun()

    st.divider()

    # KONFIGURACJA (WIDOCZNA TYLKO DLA P1)
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia Meczu")
        all_leagues = get_available_leagues()
        selected_leagues = st.multiselect("Wybierz ligi do gry:", all_leagues, default=all_leagues)
        
        if server.p1_name and server.p2_name:
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                if not selected_leagues:
                    st.error("Wybierz przynajmniej jedną ligę!")
                else:
                    load_images_filtered(selected_leagues)
                    if not server.image_pool:
                        st.error("Brak zdjęć w wybranych ligach.")
                    else:
                        start_new_round()
                        st.rerun()
        else:
            st.warning("Czekamy na drugiego gracza...")
    
    elif st.session_state.my_role == "P2":
        st.info("Czekaj, aż Gospodarz (P1) wybierze ligi i rozpocznie mecz...")
        time.sleep(2)
        st.rerun()
    
    else: # Obserwator
        time.sleep(2)
        st.rerun()

# ==============================================================================
# 2. ROZGRYWKA (PLAYING)
# ==============================================================================
elif server.status == "playing":
    
    # WYNIKI
    st.markdown(f"""
    <div class="score-board">
        <div style="color: #66bb6a">{server.p1_name}: {server.p1_score}</div>
        <div style="font-size: 16px; align-self: center; color: #aaa;">RUNDA</div>
        <div style="color: #42a5f5">{server.p2_name}: {server.p2_score}</div>
    </div>
    """, unsafe_allow_html=True)

    # INFO O BLOKADACH (Kogo tura?)
    if server.p1_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} spudłował! Teraz szansa dla: {server.p2_name}</div>", unsafe_allow_html=True)
    elif server.p2_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} spudłował! Teraz szansa dla: {server.p1_name}</div>", unsafe_allow_html=True)

    # ZDJĘCIE
    if server.current_image:
        try:
            img = Image.open(server.current_image)
            st.image(img, use_container_width=True)
        except:
            st.error("Błąd pliku.")

    # FORMULARZ
    all_teams = sorted(list(set([x[0] for x in server.image_pool])))
    user_guess = st.selectbox("Jaka to drużyna?", [""] + all_teams, key=f"g_{server.round_id}")

    c1, c2 = st.columns(2)

    # --- LOGIKA PRZYCISKÓW (Z UWZGLĘDNIENIEM BLOKAD) ---
    
    # DLA P1
    if st.session_state.my_role == "P1":
        with c1:
            # Przycisk aktywny tylko jeśli P1 NIE JEST zablokowany
            if server.p1_locked:
                st.button(f"🚫 Czekaj na ruch {server.p2_name}...", disabled=True)
            else:
                if st.button(f"Zgłaszam! ({server.p1_name})", type="primary", use_container_width=True):
                    if user_guess == server.current_team:
                        # TRAFIENIE
                        server.p1_score += 1
                        server.winner_last_round = "P1"
                        server.last_correct_answer = server.current_team
                        server.next_starter = "P1" # P1 wygrał, więc P1 klika dalej
                        server.status = "round_over"
                        st.rerun()
                    else:
                        # PUDŁO
                        st.toast("ŹLE! Blokada!", icon="❌")
                        handle_wrong_guess("P1")
                        st.rerun()
        
        with c2:
            # P1 może się poddać (działa jak pudło)
            if not server.p1_locked:
                if st.button("Poddaję turę 🏳️"):
                     handle_wrong_guess("P1")
                     st.rerun()

    # DLA P2
    elif st.session_state.my_role == "P2":
        with c2:
            # Przycisk aktywny tylko jeśli P2 NIE JEST zablokowany
            if server.p2_locked:
                st.button(f"🚫 Czekaj na ruch {server.p1_name}...", disabled=True)
            else:
                if st.button(f"Zgłaszam! ({server.p2_name})", type="primary", use_container_width=True):
                    if user_guess == server.current_team:
                        # TRAFIENIE
                        server.p2_score += 1
                        server.winner_last_round = "P2"
                        server.last_correct_answer = server.current_team
                        server.next_starter = "P2" # P2 wygrał, więc P2 klika dalej
                        server.status = "round_over"
                        st.rerun()
                    else:
                        # PUDŁO
                        st.toast("ŹLE! Blokada!", icon="❌")
                        handle_wrong_guess("P2")
                        st.rerun()
        with c1:
             if not server.p2_locked:
                if st.button("Poddaję turę 🏳️"):
                     handle_wrong_guess("P2")
                     st.rerun()

    # PRZYCISK AWARYJNY "SKIP" (Gdy obaj są zablokowani)
    if server.p1_locked and server.p2_locked:
        st.error("Obaj gracze spudłowali! Runda przepada.")
        if st.button("ZOBACZ ODPOWIEDŹ (Koniec Rundy)"):
            server.winner_last_round = "NIKT"
            server.last_correct_answer = server.current_team
            server.next_starter = "P1" # Domyślnie gospodarz
            server.status = "round_over"
            st.rerun()

    # AUTO-ODŚWIEŻANIE (żeby widzieć ruch przeciwnika)
    time.sleep(1.5)
    st.rerun()

# ==============================================================================
# 3. EKRAN KOŃCA RUNDY (ROUND OVER)
# ==============================================================================
elif server.status == "round_over":
    
    # WIDOK ODPOWIEDZI (DLA OBU GRACZY)
    if server.winner_last_round == "P1":
        st.markdown(f"<div class='winner-banner' style='background:#1b5e20; color:white'>🏆 Punkt dla {server.p1_name}!</div>", unsafe_allow_html=True)
    elif server.winner_last_round == "P2":
        st.markdown(f"<div class='winner-banner' style='background:#0d47a1; color:white'>🏆 Punkt dla {server.p2_name}!</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='winner-banner' style='background:#555; color:white'>💀 Remis / Nikt nie zgadł</div>", unsafe_allow_html=True)

    # Poprawna odpowiedź
    st.markdown("<div style='text-align:center; color:#bbb'>Poprawna odpowiedź:</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='correct-answer'>{server.last_correct_answer}</div>", unsafe_allow_html=True)
    
    # Zdjęcie (dla przypomnienia)
    if server.current_image:
        img = Image.open(server.current_image)
        st.image(img, use_container_width=True)

    st.divider()

    # PRZYCISK "DALEJ" - Widoczny TYLKO dla zwycięzcy
    if st.session_state.my_role == server.next_starter:
        st.success(f"To Ty decydujesz! Kliknij przycisk.")
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
            start_new_round()
            st.rerun()
    else:
        st.info(f"Czekaj... Gracz {server.next_starter} rozpoczyna kolejną rundę.")
        time.sleep(1.5)
        st.rerun()

# RESET AWARYJNY
if st.sidebar.button("HARD RESET"):
    reset_full_game()
    st.rerun()
    st.rerun()

