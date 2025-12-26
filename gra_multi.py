import requests
from io import BytesIO
import streamlit as st
import os
import random
import time
import pandas as pd  # <--- NOWOŚĆ: Biblioteka do obsługi CSV
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA I CSS
# ==============================================================================
st.set_page_config(page_title="Football Quiz V12 - Cloud Edition", layout="centered", page_icon="⚽")

st.markdown("""
    <style>
    /* Reset marginesów */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        max-width: 800px;
    }
    .stApp { background-color: #0e1117; }
    
    /* Ukrycie menu */
    #MainMenu, footer, header {visibility: hidden;}

    /* Tablica wyników */
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Zdjęcie */
    img {
        max-height: 400px !important;
        object-fit: contain;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    
    /* Karty graczy */
    .player-box {
        text-align: center; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold; font-size: 16px;
    }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    .solo-box { background-color: #e65100; color: #ffcc80; border: 1px solid #ef6c00; } 

    /* Alerty */
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    
    /* Przyciski */
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. STAN SERWERA (SINGLETON)
# ==============================================================================
class GlobalGameState:
    def __init__(self):
        self.mode = "multi" # "multi" lub "solo"
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" 
        
        self.current_team = None
        self.current_image = None # Teraz to będzie URL (string)
        self.image_pool = []
        self.round_id = 0
        self.input_reset_counter = 0 
        self.current_round_starter = "P1" 
        
        self.p1_locked = False
        self.p2_locked = False
        self.who_starts_next = "P1"
        self.winner_last_round = None
        self.last_correct_answer = ""
        
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.disconnect_reason = ""

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# ==============================================================================
# 3. FUNKCJE LOGIKI (ZMODYFIKOWANE POD CSV)
# ==============================================================================
CSV_FILE = "baza_zdjec.csv" # Nazwa Twojego pliku

def update_heartbeat(role):
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections():
    if server.mode == "solo": return 
    if server.status not in ["playing", "round_over"]: return
    
    timeout = 15.0
    now = time.time()
    if now - server.p1_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p2_name} rozłączył się!"

# --- NOWA FUNKCJA DO POBIERANIA LIG Z PLIKU CSV ---
def get_available_leagues(csv_path):
    if not os.path.exists(csv_path):
        return []
    try:
        # Czytamy CSV, szukamy kolumny 'Liga' i bierzemy unikalne wartości
        df = pd.read_csv(csv_path)
        if 'Liga' in df.columns:
            return sorted(df['Liga'].dropna().unique().tolist())
        return []
    except Exception as e:
        st.error(f"Błąd odczytu CSV: {e}")
        return []

# --- NOWA FUNKCJA DO ŁADOWANIA ZDJĘĆ Z PLIKU CSV ---
def load_images_filtered(csv_path, selected_leagues):
    server.image_pool = []
    if not os.path.exists(csv_path):
        return

    try:
        df = pd.read_csv(csv_path)
        # Filtrujemy tylko wybrane ligi
        filtered_df = df[df['Liga'].isin(selected_leagues)]
        
        # Iterujemy i dodajemy do puli (Klub, Link URL)
        # Zakładamy kolumny: Liga, Klub, Link_Bezposredni
        for _, row in filtered_df.iterrows():
            team = row['Klub']
            url = row['Link_Bezposredni']
            server.image_pool.append((team, url))
            
    except Exception as e:
        st.error(f"Błąd przetwarzania CSV: {e}")

def start_new_round():
    if not server.image_pool: return
    team, img_url = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img_url # Teraz to URL
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1
    server.input_reset_counter = 0 
    
    if server.mode == "solo":
        server.current_round_starter = "P1"
    else:
        server.current_round_starter = server.who_starts_next

def handle_guess(guess_text):
    if not guess_text: return False
    if guess_text == server.current_team: return True
    return False

def handle_wrong(role):
    server.input_reset_counter += 1
    if server.mode == "solo":
        return 

    if role == "P1":
        server.p1_locked = True
        server.p2_locked = False
    else:
        server.p2_locked = True
        server.p1_locked = False

def handle_surrender(role):
    server.input_reset_counter += 1
    
    if server.mode == "solo":
        server.winner_last_round = "NIKT"
        server.last_correct_answer = server.current_team
        server.status = "round_over"
        return

    if role == "P1": server.p1_locked = True
    else: server.p2_locked = True

def handle_win(winner):
    server.winner_last_round = winner
    server.last_correct_answer = server.current_team
    if winner == "P1":
        server.p1_score += 1
        server.who_starts_next = "P2"
    elif winner == "P2":
        server.p2_score += 1
        server.who_starts_next = "P1"
    server.status = "round_over"

def reset_game():
    server.mode = "multi"
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    server.p1_locked = False
    server.p2_locked = False
    server.who_starts_next = "P1"
    server.p1_last_seen = time.time()
    server.p2_last_seen = time.time()

# ==============================================================================
# 4. WIDOKI
# ==============================================================================

def view_lobby():
    st.markdown("<h2 style='text-align: center;'>🏆 LOBBY</h2>", unsafe_allow_html=True)
    
    # Sprawdzenie czy plik CSV istnieje
    if not os.path.exists(CSV_FILE):
        st.error(f"⚠️ Nie znaleziono pliku {CSV_FILE}! Wgraj go do folderu aplikacji.")
        return

    col1, col2 = st.columns(2)
    
    # P1
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"✅ {server.p1_name}")
        else:
            n1 = st.text_input("Nick:", key="n1")
            c_host, c_solo = st.columns(2)
            with c_host:
                if st.button("Hostuj (Multi)", use_container_width=True):
                    if n1:
                        server.p1_name = n1
                        server.mode = "multi"
                        st.session_state.my_role = "P1"
                        update_heartbeat("P1")
                        st.rerun()
            with c_solo:
                if st.button("Graj Sam (Solo)", use_container_width=True):
                    if n1:
                        server.p1_name = n1
                        server.mode = "solo"
                        server.p2_name = "CPU"
                        st.session_state.my_role = "P1"
                        st.rerun()

    # P2
    with col2:
        if server.mode == "solo":
             st.markdown("<div class='player-box solo-box'>TRYB JEDNOOSOBOWY</div>", unsafe_allow_html=True)
             st.info("Brak rywala.")
        else:
            st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
            if server.p2_name:
                st.success(f"✅ {server.p2_name}")
            else:
                n2 = st.text_input("Nick P2", key="n2")
                if st.button("Dołącz (P2)"):
                    if n2:
                        server.p2_name = n2
                        server.mode = "multi"
                        st.session_state.my_role = "P2"
                        update_heartbeat("P2")
                        st.rerun()

    st.divider()

    # Start Gry
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        # Pobieranie lig z CSV
        all_leagues = get_available_leagues(CSV_FILE)
        
        if not all_leagues:
            st.warning("Plik CSV jest pusty lub ma błędną strukturę (brak kolumny 'Liga').")
        
        selected_leagues = st.multiselect("Wybierz ligi:", all_leagues, default=all_leagues)
        
        st.write("") 
        
        ready = False
        if server.mode == "solo" and server.p1_name: ready = True
        elif server.mode == "multi" and server.p1_name and server.p2_name: ready = True
            
        if ready:
            if not selected_leagues:
                st.error("⚠️ Wybierz min. 1 ligę!")
            else:
                if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                    # Ładowanie z CSV
                    load_images_filtered(CSV_FILE, selected_leagues)
                    if not server.image_pool:
                        st.error("Brak zdjęć w wybranych ligach!")
                    else:
                        server.p1_last_seen = time.time()
                        server.p2_last_seen = time.time()
                        start_new_round()
                        st.rerun()
        else:
            if server.mode == "multi":
                st.warning("⏳ Czekamy na drugiego gracza...")
                time.sleep(1); st.rerun()
            
    elif st.session_state.my_role == "P2":
        st.info("⏳ Oczekiwanie na start gry..."); time.sleep(1); st.rerun()
    else:
        time.sleep(1); st.rerun()

def view_playing():
    # Wynik
    if server.mode == "solo":
        st.markdown(f"""
        <div class="score-board" style="justify-content: center;">
            <span style="color: #66bb6a">Twój Wynik: {server.p1_score}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="score-board">
            <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
            <span style="font-size: 14px; color: #888">VS</span>
            <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
        </div>
        """, unsafe_allow_html=True)

    # Info tury (Tylko Multi)
    if server.mode == "multi":
        if server.p1_locked:
            st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
        elif server.p2_locked:
            st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    # --- POPRAWIONA SEKCJA ZDJĘCIA (Wersja Pancerna) ---
    if server.current_image:
        try:
            # 1. Pobieramy plik "ręcznie" przez Python requests
            response = requests.get(server.current_image)
            response.raise_for_status() # Sprawdź czy nie ma błędu 404/403
            
            # 2. Zamieniamy pobrane bajty na obrazek
            image_data = Image.open(BytesIO(response.content))
            
            # 3. Wyświetlamy gotowy obrazek
            st.image(image_data, use_container_width=True)
            
        except Exception as e:
            st.error(f"Błąd pobierania: {e}")
            st.caption(f"Link: {server.current_image}")
    # ---------------------------------------------------

    # Pobieranie listy klubów z puli załadowanej z CSV
    # Zabezpieczenie na wypadek pustej listy
    if server.image_pool:
        all_teams = sorted(list(set([x[0] for x in server.image_pool])))
    else:
        all_teams = []

    # FORMULARZ
    with st.form(key=f"gf_{server.round_id}_{server.input_reset_counter}"):
        
        user_guess = st.selectbox("Wybierz klub:", [""] + all_teams)

        st.write("")
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            submit_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True)
        with c2:
            submit_surrender = st.form_submit_button("Poddaję🏳️", use_container_width=True)
        with c3:
            if st.session_state.my_role == "P1":
                submit_end = st.form_submit_button("🏁", type="secondary", use_container_width=True)
            else:
                submit_end = False

    # Logika formularza
    role = st.session_state.my_role
    
    if submit_end and role == "P1":
        server.status = "finished"
        st.rerun()

    if submit_guess and user_guess:
        is_locked = False
        if server.mode == "multi":
            is_locked = server.p1_locked if role == "P1" else server.p2_locked
            
        if not is_locked:
            if handle_guess(user_guess):
                handle_win(role)
                st.rerun()
            else:
                if server.mode == "multi":
                    st.toast("ŹLE!", icon="❌")
                
                handle_wrong(role)
                st.rerun()
        else:
             st.toast("Jesteś zablokowany!", icon="⛔")

    if submit_surrender:
        handle_surrender(role)
        st.rerun()

    if server.mode == "multi":
        if server.p1_locked and server.p2_locked:
            server.winner_last_round = "NIKT"
            server.last_correct_answer = server.current_team
            if server.current_round_starter == "P1": server.who_starts_next = "P2"
            else: server.who_starts_next = "P1"
            server.status = "round_over"
            st.rerun()
    if submit_surrender:
        handle_surrender(role)
        st.rerun()

    # Obsługa blokady w Multi
    if server.mode == "multi":
        if server.p1_locked and server.p2_locked:
            # ... (logika remisu) ...
            st.rerun()

    # --- ZMIANA TUTAJ: Migotanie tylko w Multi ---
    if server.mode == "multi":
        time.sleep(1)
        st.rerun()
def view_round_over():
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ", type="primary"):
            server.status = "finished"
            st.rerun()

    if server.winner_last_round == "P1":
        bg, txt = "#1b5e20", f"🏆 Punkt dla: {server.p1_name}!"
    elif server.winner_last_round == "P2":
        bg, txt = "#0d47a1", f"🏆 Punkt dla: {server.p2_name}!"
    else:
        bg, txt = "#555", "💀 Nikt nie zgadł"
        
    st.markdown(f"""
    <div style='background-color:{bg}; color:white; padding:15px; border-radius:10px; text-align:center; font-size:24px; font-weight:bold; margin-bottom:10px;'>
        {txt}
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<h3 style='text-align:center; color:#4CAF50;'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    # --- TUTAJ ZMIANA: PANCERNE ŁADOWANIE ZDJĘCIA ---
    if server.current_image: 
        try:
            response = requests.get(server.current_image)
            response.raise_for_status()
            image_data = Image.open(BytesIO(response.content))
            st.image(image_data, use_container_width=True)
        except Exception as e:
            st.warning(f"Nie udało się załadować zdjęcia w podsumowaniu.")
    # ------------------------------------------------

    st.divider()

    # Przycisk Dalej
    if server.mode == "solo":
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
            start_new_round()
            st.rerun()
    else:
        active_player = server.who_starts_next
        if st.session_state.my_role == active_player:
            st.success("Twoja kolej!")
            if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
                start_new_round()
                st.rerun()
        else:
            st.info(f"Czekaj... {active_player} rozpoczyna rundę."); st.empty(); time.sleep(1); st.rerun()

def view_disconnected():
    st.error(f"🚨 WALKOWER! {server.disconnect_reason}")
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"):
        reset_game()
        st.rerun()
    time.sleep(2)
    st.rerun()

def view_finished():
    st.markdown("<h1 style='text-align:center'>KONIEC MECZU</h1>", unsafe_allow_html=True)
    if server.mode == "solo":
        st.markdown(f"<h2 style='text-align:center'>Twój wynik: {server.p1_score}</h2>", unsafe_allow_html=True)
    else:
        if server.p1_score > server.p2_score: msg = f"🏆 WYGRYWA: {server.p1_name}!"
        elif server.p2_score > server.p1_score: msg = f"🏆 WYGRYWA: {server.p2_name}!"
        else: msg = "🤝 REMIS!"
        st.markdown(f"<h2 style='text-align:center;'>{msg}</h2>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='background-color:#262730; padding:20px; border-radius:10px; text-align:center; margin-top:20px;'>
            <h1>{server.p1_score} - {server.p2_score}</h1>
        </div>
        """, unsafe_allow_html=True)

    if st.button("ZAGRAJ JESZCZE RAZ (LOBBY) 🔄", type="primary", use_container_width=True):
        reset_game()
        st.rerun()

# ==============================================================================
# 5. MAIN
# ==============================================================================
def main():
    if 'my_role' not in st.session_state: st.session_state.my_role = None

    if st.session_state.my_role:
        update_heartbeat(st.session_state.my_role)
    check_disconnections()

    # Reset awaryjny
    if st.sidebar.button("HARD RESET"):
        reset_game()
        st.rerun()

    if server.status == "lobby": view_lobby()
    elif server.status == "playing": view_playing()
    elif server.status == "round_over": view_round_over()
    elif server.status == "finished": view_finished()
    elif server.status == "disconnected": view_disconnected()

if __name__ == "__main__":
    main()






