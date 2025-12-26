import streamlit as st
import os
import random
import time
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA
# ==============================================================================
st.set_page_config(page_title="Football Quiz Ultimate", layout="centered", page_icon="⚽")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 5rem !important; max-width: 800px; }
    .stApp { background-color: #0e1117; }
    #MainMenu, footer, header {visibility: hidden;}
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    img { max-height: 400px !important; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

# Lista Top 20 - musi pasować do nazw folderów (Klubów) w CSV
TOP_20_CLUBS = [
    "Manchester City", "Real Madrid", "Bayern Munich", "Liverpool", "Inter Milan",
    "Bayer Leverkusen", "Arsenal", "Barcelona", "Atletico Madrid", "PSG",
    "Borussia Dortmund", "Juventus", "RB Leipzig", "Atalanta", "Benfica",
    "Chelsea", "AC Milan", "Sporting CP", "Napoli", "Tottenham"
]

# ==============================================================================
# 2. STAN SERWERA
# ==============================================================================
class GlobalGameState:
    def __init__(self):
        self.mode = "multi"
        self.p1_name = None; self.p2_name = None
        self.p1_score = 0; self.p2_score = 0
        self.status = "lobby"
        self.current_team = None; self.current_image = None
        self.image_pool = []; self.round_id = 0; self.input_reset_counter = 0
        self.current_round_starter = "P1"; self.who_starts_next = "P1"
        self.p1_locked = False; self.p2_locked = False
        self.winner_last_round = None; self.last_correct_answer = ""
        self.p1_last_seen = time.time(); self.p2_last_seen = time.time()
        self.disconnect_reason = ""
        self.active_category_name = "👕 Koszulki (Ligi)"

@st.cache_resource
def get_server_state(): return GlobalGameState()
server = get_server_state()

# Konfiguracja Trybów
GAME_MODES = {
    "👕 Koszulki (Ligi)": ("baza_zdjec.csv", "Jaki to klub?"),
    "👤 Sylwetki Piłkarzy": ("sylwetki_pilkarzy.csv", "Kto to jest?"),
    "🛡️ Herby Klubowe": ("herby_klubowe.csv", "Do kogo należy ten herb?")
}

def update_heartbeat(role):
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections():
    if server.mode == "solo" or server.status not in ["playing", "round_over"]: return
    now = time.time()
    if now - server.p1_last_seen > 15: server.status="disconnected"; server.disconnect_reason=f"{server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > 15: server.status="disconnected"; server.disconnect_reason=f"{server.p2_name} rozłączył się!"

def get_available_leagues(csv_path):
    if not os.path.exists(csv_path): return []
    try:
        df = pd.read_csv(csv_path)
        if 'Liga' in df.columns: return sorted(df['Liga'].dropna().unique().tolist())
        return []
    except: return []

def load_images_filtered(csv_path, selected_leagues, use_top_20_filter=False):
    server.image_pool = []
    if not os.path.exists(csv_path): return

    try:
        df = pd.read_csv(csv_path)
        
        # 1. Filtrowanie po ligach
        if selected_leagues:
            df = df[df['Liga'].isin(selected_leagues)]
        
        # 2. Filtr Top 20 (opcjonalny)
        if use_top_20_filter:
            # Sprawdzamy czy mamy kolumnę "Klub_Filter" (z nowego skryptu sylwetek)
            if 'Klub_Filter' in df.columns:
                df = df[df['Klub_Filter'].isin(TOP_20_CLUBS)]
            # Jeśli nie, sprawdzamy kolumnę "Klub" (stary plik koszulek)
            # Uwaga: w sylwetkach kolumna 'Klub' może nazywać się 'Odpowiedz' w zależności od skryptu.
            # Tutaj zakładam, że dla koszulek to 'Klub' lub 'Odpowiedz' zawierająca nazwę klubu.
            elif 'Klub' in df.columns:
                df = df[df['Klub'].isin(TOP_20_CLUBS)]
            elif 'Odpowiedz' in df.columns: # Dla kompatybilności
                 df = df[df['Odpowiedz'].isin(TOP_20_CLUBS)]
        
        # 3. Zapisywanie do puli
        # Szukamy kolumny z odpowiedzią (może być 'Klub' lub 'Odpowiedz')
        ans_col = 'Odpowiedz' if 'Odpowiedz' in df.columns else 'Klub'
        link_col = 'Link_Bezposredni'
        
        for _, row in df.iterrows():
            server.image_pool.append((row[ans_col], row[link_col]))
            
    except Exception as e:
        st.error(f"Błąd CSV: {e}")

def start_new_round():
    if not server.image_pool: return
    team, img_url = random.choice(server.image_pool)
    server.current_team = team; server.current_image = img_url
    server.p1_locked = False; server.p2_locked = False
    server.status = "playing"; server.winner_last_round = None
    server.round_id += 1; server.input_reset_counter = 0
    if server.mode == "solo": server.current_round_starter = "P1"
    else: server.current_round_starter = server.who_starts_next

def handle_guess(guess): return guess == server.current_team
def handle_wrong(role):
    server.input_reset_counter += 1
    if server.mode == "solo": return
    if role == "P1": server.p1_locked = True; server.p2_locked = False
    else: server.p2_locked = True; server.p1_locked = False
def handle_surrender(role):
    server.input_reset_counter += 1
    if server.mode == "solo": server.winner_last_round="NIKT"; server.last_correct_answer=server.current_team; server.status="round_over"; return
    if role == "P1": server.p1_locked = True
    else: server.p2_locked = True
def handle_win(winner):
    server.winner_last_round = winner; server.last_correct_answer = server.current_team
    if winner == "P1": server.p1_score += 1; server.who_starts_next = "P2"
    else: server.p2_score += 1; server.who_starts_next = "P1"
    server.status = "round_over"
def reset_game():
    server.mode="multi"; server.p1_name=None; server.p2_name=None; server.p1_score=0; server.p2_score=0
    server.status="lobby"; server.p1_locked=False; server.p2_locked=False; server.who_starts_next="P1"

# ==============================================================================
# 3. WIDOKI
# ==============================================================================
def view_lobby():
    st.markdown("<h2 style='text-align: center;'>🏆 LOBBY</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name: st.success(f"✅ {server.p1_name}")
        else:
            n = st.text_input("Nick P1", key="n1")
            cc1, cc2 = st.columns(2)
            if cc1.button("Host"): 
                if n: server.p1_name=n; server.mode="multi"; st.session_state.my_role="P1"; st.rerun()
            if cc2.button("Solo"): 
                if n: server.p1_name=n; server.mode="solo"; server.p2_name="CPU"; st.session_state.my_role="P1"; st.rerun()
    with c2:
        if server.mode=="solo": st.info("Tryb Solo")
        else:
            st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
            if server.p2_name: st.success(f"✅ {server.p2_name}")
            else:
                n = st.text_input("Nick P2", key="n2")
                if st.button("Dołącz"): 
                    if n: server.p2_name=n; server.mode="multi"; st.session_state.my_role="P2"; st.rerun()

    st.divider()
    
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        mode = st.selectbox("Wybierz tryb:", list(GAME_MODES.keys()))
        csv_file, _ = GAME_MODES[mode]
        
        # Wybór Lig
        all_leagues = get_available_leagues(csv_file)
        sel_leagues = st.multiselect("Wybierz ligi:", all_leagues, default=all_leagues)
        
        # NOWOŚĆ: CHECKBOX FILTRA
        use_top20 = st.checkbox("🏆 Tylko kluby z Top 20 (Ranking)", value=False)
        
        ready = (server.mode=="solo" and server.p1_name) or (server.mode=="multi" and server.p1_name and server.p2_name)
        
        if ready:
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                if not sel_leagues: st.error("Wybierz ligę!")
                else:
                    load_images_filtered(csv_file, sel_leagues, use_top20)
                    server.active_category_name = mode
                    if not server.image_pool: st.error(f"Brak zdjęć! (Może filtr Top 20 wykluczył wszystko? Sprawdź nazwy klubów w CSV i w liście TOP_20_CLUBS)")
                    else: server.p1_last_seen=time.time(); server.p2_last_seen=time.time(); start_new_round(); st.rerun()
        elif server.mode == "multi": st.warning("Czekamy na P2...")
            
    elif st.session_state.my_role == "P2": st.info("Czekanie na hosta..."); time.sleep(1); st.rerun()
    else: time.sleep(1); st.rerun()

def view_playing():
    _, q_label = GAME_MODES.get(server.active_category_name, ("", "Wybierz:"))
    st.caption(f"Tryb: {server.active_category_name}")
    
    if server.mode=="solo": st.markdown(f"<div class='score-board' style='justify-content:center'>{server.p1_score}</div>", unsafe_allow_html=True)
    else: st.markdown(f"<div class='score-board'><span>{server.p1_name}: {server.p1_score}</span><span>VS</span><span>{server.p2_name}: {server.p2_score}</span></div>", unsafe_allow_html=True)
    
    if server.mode=="multi":
        if server.p1_locked: st.warning(f"{server.p1_name} zablokowany!")
        elif server.p2_locked: st.warning(f"{server.p2_name} zablokowany!")

    if server.current_image:
        try:
            r = requests.get(server.current_image); r.raise_for_status()
            st.image(Image.open(BytesIO(r.content)), use_container_width=True)
        except: st.error("Błąd zdjęcia")

    opts = sorted(list(set([x[0] for x in server.image_pool]))) if server.image_pool else []
    
    with st.form(f"gf_{server.round_id}_{server.input_reset_counter}"):
        guess = st.selectbox(q_label, [""]+opts)
        c1, c2 = st.columns([3,1])
        sub = c1.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True)
        surr = c2.form_submit_button("🏳️", use_container_width=True)
        if st.session_state.my_role=="P1": st.form_submit_button("Koniec", on_click=lambda: setattr(server,'status','finished'))

    role = st.session_state.my_role
    if sub and guess:
        locked = (role=="P1" and server.p1_locked) or (role=="P2" and server.p2_locked)
        if not locked:
            if handle_guess(guess): handle_win(role); st.rerun()
            else: handle_wrong(role); st.toast("ŹLE!"); st.rerun()
        else: st.toast("Czekaj!")
    if surr: handle_surrender(role); st.rerun()
    
    if server.mode=="multi":
        if server.p1_locked and server.p2_locked:
            server.winner_last_round="NIKT"; server.last_correct_answer=server.current_team
            server.who_starts_next = "P2" if server.current_round_starter=="P1" else "P1"
            server.status="round_over"; st.rerun()
        time.sleep(1); st.rerun()

def view_round_over():
    if st.session_state.my_role=="P1" and st.sidebar.button("Zakończ"): server.status="finished"; st.rerun()
    
    col, txt = ("#555", "Nikt")
    if server.winner_last_round=="P1": col, txt = ("#1b5e20", server.p1_name)
    elif server.winner_last_round=="P2": col, txt = ("#0d47a1", server.p2_name)
    
    st.markdown(f"<div style='background:{col}; color:white; padding:10px; text-align:center'>Punkt: {txt}</div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    if server.current_image:
        try: st.image(Image.open(BytesIO(requests.get(server.current_image).content)), use_container_width=True)
        except: pass

    st.divider()
    nxt = server.who_starts_next if server.mode=="multi" else "P1"
    if st.session_state.my_role == nxt:
        if st.button("DALEJ ➡️", type="primary", use_container_width=True): start_new_round(); st.rerun()
    else: st.info(f"Czekaj na {nxt}..."); time.sleep(1); st.rerun()

def view_finished():
    st.title("KONIEC"); st.header(f"{server.p1_score} - {server.p2_score}")
    if st.button("LOBBY"): reset_game(); st.rerun()

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










