import streamlit as st
import os
import random
import time
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA I STYL (CSS)
# ==============================================================================
st.set_page_config(page_title="Football Quiz Ultimate", layout="centered", page_icon="⚽")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 5rem !important; max-width: 800px; }
    .stApp { background-color: #0e1117; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Tablica wyników */
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Styl obrazka */
    img { max-height: 400px !important; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
    
    /* Gracze */
    .player-box { text-align: center; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold; font-size: 16px; }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    .solo-box { background-color: #e65100; color: #ffcc80; border: 1px solid #ef6c00; } 
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    
    /* Przyciski */
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. LISTA TOP 20 (RANKING KLUBOWY)
# ==============================================================================
# UWAGA: Nazwy muszą być IDENTYCZNE jak w pliku baza_zdjec.csv (w kolumnie Klub)
TOP_20_CLUBS = [
    "Manchester City", "Real Madrid", "Bayern Munich", "Liverpool", "Inter Milan",
    "Bayer Leverkusen", "Arsenal", "Barcelona", "Atletico Madrid", "PSG",
    "Borussia Dortmund", "Juventus", "RB Leipzig", "Atalanta", "Benfica",
    "Chelsea", "AC Milan", "Sporting CP", "Napoli", "Tottenham"
]

# ==============================================================================
# 3. ZARZĄDZANIE STANEM GRY
# ==============================================================================
class GlobalGameState:
    def __init__(self):
        self.mode = "multi"
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" 
        
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        self.input_reset_counter = 0 
        self.current_round_starter = "P1" 
        self.who_starts_next = "P1"
        
        self.p1_locked = False
        self.p2_locked = False
        self.winner_last_round = None
        self.last_correct_answer = ""
        
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.disconnect_reason = ""
        
        # Przechowuje nazwę aktualnego trybu
        self.active_category_name = "👕 Koszulki (Ligi)"

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# ==============================================================================
# 4. LOGIKA GRY
# ==============================================================================

# Konfiguracja trybów: "Nazwa w Menu": ("Nazwa Pliku CSV", "Pytanie do gracza")
GAME_MODES = {
    "👕 Koszulki (Ligi)": ("baza_zdjec.csv", "Jaki to klub?"),
    "🏆 Top 20 (Ranking)": ("baza_zdjec.csv", "Jaki to klub?"), 
    "👤 Sylwetki Piłkarzy": ("sylwetki_pilkarzy.csv", "Kto to jest?")
}

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

def get_available_leagues(csv_path):
    if not os.path.exists(csv_path): return []
    try:
        df = pd.read_csv(csv_path)
        if 'Liga' in df.columns: return sorted(df['Liga'].dropna().unique().tolist())
        return []
    except: return []

def load_images_filtered(csv_path, selected_leagues=None, top_20_mode=False):
    server.image_pool = []
    if not os.path.exists(csv_path): return

    try:
        df = pd.read_csv(csv_path)
        
        # 1. Tryb TOP 20: Filtrujemy po nazwach klubów
        if top_20_mode:
            filtered_df = df[df['Klub'].isin(TOP_20_CLUBS)]
        
        # 2. Tryb Normalny: Filtrujemy po wybranych ligach
        else:
            if selected_leagues:
                filtered_df = df[df['Liga'].isin(selected_leagues)]
            else:
                filtered_df = pd.DataFrame() # Pusto jeśli nic nie wybrano
        
        # Zapisujemy do puli gry
        for _, row in filtered_df.iterrows():
            team = row['Klub'] # To może być "Arsenal" albo "Álex Baena"
            url = row['Link_Bezposredni']
            server.image_pool.append((team, url))
            
    except Exception as e:
        st.error(f"Błąd CSV: {e}")

def start_new_round():
    if not server.image_pool: return
    team, img_url = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img_url
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1
    server.input_reset_counter = 0 
    
    if server.mode == "solo": server.current_round_starter = "P1"
    else: server.current_round_starter = server.who_starts_next

def handle_guess(guess_text):
    if not guess_text: return False
    # Porównujemy tekst z CSV (Klub/Piłkarz) z tym co wybrał użytkownik
    if guess_text == server.current_team: return True
    return False

def handle_wrong(role):
    server.input_reset_counter += 1
    if server.mode == "solo": return 
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
# 5. WIDOKI (UI)
# ==============================================================================

def view_lobby():
    st.markdown("<h2 style='text-align: center;'>🏆 LOBBY</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    # KARTA GRACZA 1
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name: st.success(f"✅ {server.p1_name}")
        else:
            n1 = st.text_input("Nick:", key="n1")
            c1, c2 = st.columns(2)
            with c1: 
                if st.button("Hostuj", use_container_width=True): 
                    if n1: server.p1_name=n1; server.mode="multi"; st.session_state.my_role="P1"; update_heartbeat("P1"); st.rerun()
            with c2:
                if st.button("Solo", use_container_width=True):
                    if n1: server.p1_name=n1; server.mode="solo"; server.p2_name="CPU"; st.session_state.my_role="P1"; st.rerun()

    # KARTA GRACZA 2
    with col2:
        if server.mode == "solo":
             st.markdown("<div class='player-box solo-box'>TRYB SOLO</div>", unsafe_allow_html=True); st.info("Brak rywala.")
        else:
            st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
            if server.p2_name: st.success(f"✅ {server.p2_name}")
            else:
                n2 = st.text_input("Nick P2", key="n2")
                if st.button("Dołącz"): 
                    if n2: server.p2_name=n2; server.mode="multi"; st.session_state.my_role="P2"; update_heartbeat("P2"); st.rerun()

    st.divider()

    # --- KONFIGURACJA MECZU (Widzi tylko P1) ---
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia Meczu")
        
        # Wybór Trybu (Klucze ze słownika GAME_MODES)
        mode_key = st.selectbox("Wybierz tryb gry:", list(GAME_MODES.keys()))
        csv_file, question_label = GAME_MODES[mode_key]
        
        # Walidacja pliku
        if not os.path.exists(csv_file):
            st.error(f"⚠️ Nie znaleziono pliku: {csv_file}. Wgraj go do folderu!")
            return

        # Scenariusz A: Ranking Top 20
        if "Top 20" in mode_key:
            st.info(f"🏆 Wybrano tryb Rankingowy. Losujemy spośród 20 najlepszych klubów.")
            ready = True if (server.mode=="solo" and server.p1_name) or (server.mode=="multi" and server.p1_name and server.p2_name) else False
            
            if ready:
                if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                    load_images_filtered(csv_file, top_20_mode=True)
                    server.active_category_name = mode_key
                    if not server.image_pool: st.error("Brak zdjęć Top 20! (Sprawdź czy nazwy w kodzie w liście TOP_20_CLUBS są takie same jak w CSV)")
                    else: server.p1_last_seen=time.time(); server.p2_last_seen=time.time(); start_new_round(); st.rerun()
        
        # Scenariusz B: Koszulki lub Sylwetki (Wybór Lig)
        else:
            all_leagues = get_available_leagues(csv_file)
            if not all_leagues: st.warning("Plik CSV wydaje się pusty.")
            
            sel_leagues = st.multiselect("Wybierz ligi/kategorie:", all_leagues, default=all_leagues)
            
            ready = True if (server.mode=="solo" and server.p1_name) or (server.mode=="multi" and server.p1_name and server.p2_name) else False
            if ready:
                if not sel_leagues: st.error("Wybierz przynajmniej jedną ligę!")
                else:
                    if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                        load_images_filtered(csv_file, selected_leagues=sel_leagues)
                        server.active_category_name = mode_key
                        if not server.image_pool: st.error("Brak zdjęć w wybranych kategoriach!")
                        else: server.p1_last_seen=time.time(); server.p2_last_seen=time.time(); start_new_round(); st.rerun()
        
        if not ready and server.mode == "multi":
             st.warning("Czekamy na drugiego gracza...")
             time.sleep(1); st.rerun()
            
    elif st.session_state.my_role == "P2":
        st.info("Czekanie na hosta..."); time.sleep(1); st.rerun()
    else: time.sleep(1); st.rerun()

def view_playing():
    # Pobieramy właściwe pytanie (np. "Kto to jest?")
    _, question_label = GAME_MODES.get(server.active_category_name, ("", "Wybierz:"))
    
    st.caption(f"Tryb: {server.active_category_name}")
    
    # WYNIKI
    if server.mode == "solo":
        st.markdown(f"<div class='score-board' style='justify-content:center; color:#66bb6a'>Twój Wynik: {server.p1_score}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class='score-board'><span style='color:#66bb6a'>{server.p1_name}: {server.p1_score}</span><span style='color:#888'>VS</span><span style='color:#42a5f5'>{server.p2_name}: {server.p2_score}</span></div>""", unsafe_allow_html=True)

    # ALERTY TURY
    if server.mode == "multi":
        if server.p1_locked: st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
        elif server.p2_locked: st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    # ZDJĘCIE (METODA PANCERNA)
    if server.current_image:
        try:
            r = requests.get(server.current_image); r.raise_for_status()
            st.image(Image.open(BytesIO(r.content)), use_container_width=True)
        except: st.error("Nie udało się załadować zdjęcia")

    # LISTA ODPOWIEDZI (KLUBY LUB PIŁKARZE)
    # Lista jest pobierana dynamicznie z tego, co załadowaliśmy do image_pool
    all_options = sorted(list(set([x[0] for x in server.image_pool]))) if server.image_pool else []

    # FORMULARZ
    with st.form(key=f"gf_{server.round_id}_{server.input_reset_counter}"):
        # Dynamiczna etykieta (np. "Kto to jest?")
        user_guess = st.selectbox(question_label, [""] + all_options)
        
        c1, c2 = st.columns([3, 1])
        with c1: sub_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True)
        with c2: sub_surr = st.form_submit_button("🏳️", use_container_width=True)
        if st.session_state.my_role == "P1": st.form_submit_button("Zakończ Mecz", on_click=lambda: setattr(server, 'status', 'finished'))

    role = st.session_state.my_role
    
    # Logika sprawdzania
    if sub_guess and user_guess:
        is_locked = (role=="P1" and server.p1_locked) or (role=="P2" and server.p2_locked) if server.mode=="multi" else False
        if not is_locked:
            if handle_guess(user_guess): handle_win(role); st.rerun()
            else: 
                if server.mode=="multi": st.toast("ŹLE!", icon="❌")
                handle_wrong(role); st.rerun()
        else: st.toast("Zablokowany!", icon="⛔")

    if sub_surr: handle_surrender(role); st.rerun()

    # Synchronizacja Multi
    if server.mode == "multi":
        if server.p1_locked and server.p2_locked:
            server.winner_last_round="NIKT"; server.last_correct_answer=server.current_team
            server.who_starts_next = "P2" if server.current_round_starter == "P1" else "P1"
            server.status = "round_over"; st.rerun()
        time.sleep(1); st.rerun()

def view_round_over():
    if st.session_state.my_role == "P1":
        if st.sidebar.button("Zakończ", type="primary"): server.status="finished"; st.rerun()

    bg, txt = ("#555", "💀 Nikt nie zgadł")
    if server.winner_last_round == "P1": bg, txt = ("#1b5e20", f"🏆 Punkt: {server.p1_name}")
    elif server.winner_last_round == "P2": bg, txt = ("#0d47a1", f"🏆 Punkt: {server.p2_name}")
        
    st.markdown(f"<div style='background:{bg}; color:white; padding:15px; border-radius:10px; text-align:center;'><h3>{txt}</h3></div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center; color:#4CAF50;'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    # Wyświetlenie zdjęcia w podsumowaniu (Pancerna metoda)
    if server.current_image:
        try:
            r = requests.get(server.current_image); r.raise_for_status()
            st.image(Image.open(BytesIO(r.content)), use_container_width=True)
        except: pass

    st.divider()
    
    # Przycisk Dalej
    nxt = server.who_starts_next if server.mode == "multi" else "P1"
    if st.session_state.my_role == nxt:
        if st.button("DALEJ ➡️", type="primary", use_container_width=True): start_new_round(); st.rerun()
    else: st.info(f"Czekaj na {nxt}..."); time.sleep(1); st.rerun()

def view_finished():
    st.markdown("<h1 style='text-align:center'>KONIEC MECZU</h1>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center'>{server.p1_score} - {server.p2_score}</h2>", unsafe_allow_html=True)
    if st.button("LOBBY 🔄", type="primary", use_container_width=True): reset_game(); st.rerun()

def view_disconnected():
    st.error(f"🚨 WALKOWER! {server.disconnect_reason}")
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"): reset_game(); st.rerun()
    time.sleep(2); st.rerun()

def main():
    if 'my_role' not in st.session_state: st.session_state.my_role = None
    if st.session_state.my_role: update_heartbeat(st.session_state.my_role)
    check_disconnections()
    if st.sidebar.button("RESET"): reset_game(); st.rerun()

    if server.status == "lobby": view_lobby()
    elif server.status == "playing": view_playing()
    elif server.status == "round_over": view_round_over()
    elif server.status == "finished": view_finished()
    elif server.status == "disconnected": view_disconnected()

if __name__ == "__main__":
    main()








