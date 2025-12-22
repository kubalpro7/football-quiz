import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "." 

# Ustawienie layoutu na 'wide' pomaga w responsywności, ale 'centered' jest lepsze do skupienia wzroku.
# Zostajemy przy centered, ale zmieniamy CSS marginesów.
st.set_page_config(page_title="Football Quiz FINAL", layout="centered", page_icon="⚽")

# --- CSS (KOMPAKTOWY WYGLĄD) ---
st.markdown("""
    <style>
    /* 1. Zmniejszenie marginesów góry strony (żeby wszystko weszło na ekran) */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 800px;
    }
    
    /* 2. Tło i ogólny styl */
    .stApp { background-color: #0e1117; }
    
    /* 3. Tablica wyników - mniejsza i bardziej kompaktowa */
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 10px 20px; border-radius: 8px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 10px;
    }
    
    /* 4. Ograniczenie wielkości zdjęcia (kluczowe dla laptopów) */
    img {
        max-height: 350px !important;
        object-fit: contain;
        border-radius: 10px;
    }
    
    /* 5. Style kart graczy */
    .player-box {
        text-align: center; padding: 5px; border-radius: 5px; width: 100%; font-weight: bold; font-size: 14px;
    }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    
    /* 6. Alert o turze */
    .turn-alert {
        text-align: center; color: #ffca28; font-weight: bold; font-size: 16px; margin: 5px 0;
    }
    
    /* 7. Banner zwycięzcy */
    .winner-banner {
        background-color: #ffd700; color: black; padding: 10px;
        text-align: center; border-radius: 8px; font-size: 20px; font-weight: bold;
        margin-bottom: 10px;
    }
    .correct-answer {
        font-size: 24px; color: #4CAF50; text-align: center; font-weight: bold; margin-bottom: 10px;
    }
    
    /* Ukrycie standardowego menu Streamlit dla czystszego widoku */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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
        
        # Logika tur
        self.p1_locked = False
        self.p2_locked = False
        
        # Logika "Kto zaczyna"
        self.who_starts_next = "P1" # Domyślnie P1 na start gry
        
        # Koniec rundy
        self.winner_last_round = None
        self.last_correct_answer = ""

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# --- LOKALNY STAN ---
if 'my_role' not in st.session_state:
    st.session_state.my_role = None

# --- FUNKCJE LOGIKI ---
def get_available_leagues():
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return []
    leagues = []
    for item in os.listdir(FOLDER_Z_KOSZULKAMI):
        if os.path.isdir(os.path.join(FOLDER_Z_KOSZULKAMI, item)) and not item.startswith("."):
            leagues.append(item.replace("_", " "))
    return sorted(leagues)

def load_images_filtered(selected_leagues):
    server.image_pool = []
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return
    for root, dirs, files in os.walk(FOLDER_Z_KOSZULKAMI):
        folder_parts = root.split(os.sep)
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
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    
    # Reset blokad
    server.p1_locked = False
    server.p2_locked = False
    
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1

def handle_wrong_guess(player_role):
    if player_role == "P1":
        server.p1_locked = True
        server.p2_locked = False
    else:
        server.p2_locked = True
        server.p1_locked = False

def handle_round_win(winner_role):
    server.winner_last_round = winner_role
    server.last_correct_answer = server.current_team
    
    if winner_role == "P1":
        server.p1_score += 1
        server.who_starts_next = "P2" # P1 wygrał -> P2 zaczyna następną (przegrany zaczyna)
    elif winner_role == "P2":
        server.p2_score += 1
        server.who_starts_next = "P1" # P2 wygrał -> P1 zaczyna następną
    
    server.status = "round_over"

def reset_full_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    server.p1_locked = False
    server.p2_locked = False
    server.who_starts_next = "P1"

# ==============================================================================
# 1. LOBBY (Konfiguracja)
# ==============================================================================
if server.status == "lobby":
    st.title("🏆 Football Quiz: LOBBY")
    st.info("👋 Dołącz do gry.")
    
    col1, col2 = st.columns(2)
    
    # KARTA P1
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"✅ {server.p1_name}")
            if st.session_state.my_role == "P1": st.caption("(To Ty)")
        else:
            nick1 = st.text_input("Nick P1", key="n1", placeholder="Wpisz nick...")
            if st.button("Zajmij P1"):
                if nick1:
                    server.p1_name = nick1
                    st.session_state.my_role = "P1"
                    st.rerun()

    # KARTA P2
    with col2:
        st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
        if server.p2_name:
            st.success(f"✅ {server.p2_name}")
            if st.session_state.my_role == "P2": st.caption("(To Ty)")
        else:
            nick2 = st.text_input("Nick P2", key="n2", placeholder="Wpisz nick...")
            if st.button("Zajmij P2"):
                if nick2:
                    server.p2_name = nick2
                    st.session_state.my_role = "P2"
                    st.rerun()

    st.divider()

    # WYBÓR LIG I START (Tylko dla P1 i tylko w lobby)
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Wybierz ligi")
        all_leagues = get_available_leagues()
        selected_leagues = st.multiselect("Ligi:", all_leagues, default=all_leagues)
        
        if server.p1_name and server.p2_name:
            st.markdown("---")
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                if not selected_leagues:
                    st.error("Wybierz min. 1 ligę!")
                else:
                    load_images_filtered(selected_leagues)
                    if not server.image_pool:
                        st.error("Brak zdjęć!")
                    else:
                        start_new_round() # Status zmieni się na 'playing'
                        st.rerun()
        else:
            st.warning("Czekamy na drugiego gracza...")
    
    elif st.session_state.my_role == "P2":
        st.info("Czekaj na start gry przez Gospodarza...")
        time.sleep(2)
        st.rerun()
    else:
        time.sleep(2)
        st.rerun()

# ==============================================================================
# 2. ROZGRYWKA (PLAYING)
# ==============================================================================
elif server.status == "playing":
    
    # WYNIKI (Kompaktowe)
    st.markdown(f"""
    <div class="score-board">
        <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span style="font-size: 14px; color: #888">RUNDA {server.p1_score + server.p2_score + 1}</span>
        <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)

    # INFO O BLOKADACH
    if server.p1_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} spudłował! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
    elif server.p2_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} spudłował! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    # ZDJĘCIE
    if server.current_image:
        try:
            img = Image.open(server.current_image)
            st.image(img, use_container_width=True)
        except:
            st.error("Błąd pliku.")

    # FORMULARZ ODPOWIEDZI
    all_teams = sorted(list(set([x[0] for x in server.image_pool])))
    user_guess = st.selectbox("Wybierz drużynę:", [""] + all_teams, key=f"g_{server.round_id}")

    # PRZYCISKI AKCJI
    c1, c2 = st.columns(2)

    # Logika dla P1
    if st.session_state.my_role == "P1":
        with c1:
            if server.p1_locked:
                st.button(f"⏳ Czekaj...", disabled=True, use_container_width=True)
            else:
                if st.button("ZGŁASZAM! 🎯", type="primary", use_container_width=True):
                    if user_guess == server.current_team:
                        handle_round_win("P1")
                        st.rerun()
                    else:
                        st.toast("ŹLE!", icon="❌")
                        handle_wrong_guess("P1")
                        st.rerun()
        with c2:
             if not server.p1_locked:
                if st.button("Poddaję turę 🏳️", use_container_width=True):
                     handle_wrong_guess("P1")
                     st.rerun()

    # Logika dla P2
    elif st.session_state.my_role == "P2":
        with c2:
            if server.p2_locked:
                st.button(f"⏳ Czekaj...", disabled=True, use_container_width=True)
            else:
                if st.button("ZGŁASZAM! 🎯", type="primary", use_container_width=True):
                    if user_guess == server.current_team:
                        handle_round_win("P2")
                        st.rerun()
                    else:
                        st.toast("ŹLE!", icon="❌")
                        handle_wrong_guess("P2")
                        st.rerun()
        with c1:
             if not server.p2_locked:
                if st.button("Poddaję turę 🏳️", use_container_width=True):
                     handle_wrong_guess("P2")
                     st.rerun()

    # SKIP (Gdy obaj zablokowani)
    if server.p1_locked and server.p2_locked:
        st.warning("Obaj spudłowali!")
        if st.button("POKAŻ ODPOWIEDŹ (Koniec Rundy)", use_container_width=True):
            server.winner_last_round = "NIKT"
            server.last_correct_answer = server.current_team
            # Jeśli nikt nie wygrał, zasada przegranego nie działa wprost.
            # Zostawmy prawo startu temu, kto miał je ostatnio (lub domyślnie P1)
            server.status = "round_over"
            st.rerun()

    time.sleep(1.0)
    st.rerun()

# ==============================================================================
# 3. KONIEC RUNDY (ROUND OVER)
# ==============================================================================
elif server.status == "round_over":
    
    # WYNIKI
    st.markdown(f"""
    <div class="score-board">
        <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # INFO O ZWYCIĘZCY
    if server.winner_last_round == "P1":
        st.markdown(f"<div class='winner-banner' style='background:#1b5e20; color:white'>🏆 Punkt dla {server.p1_name}!</div>", unsafe_allow_html=True)
    elif server.winner_last_round == "P2":
        st.markdown(f"<div class='winner-banner' style='background:#0d47a1; color:white'>🏆 Punkt dla {server.p2_name}!</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='winner-banner' style='background:#555; color:white'>💀 Remis / Nikt nie zgadł</div>", unsafe_allow_html=True)

    # POPRAWNA ODPOWIEDŹ
    st.markdown("<div style='text-align:center; color:#bbb; font-size:14px'>Poprawna odpowiedź:</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='correct-answer'>{server.last_correct_answer}</div>", unsafe_allow_html=True)
    
    # ZDJĘCIE (Mniejsze dla przypomnienia)
    if server.current_image:
        img = Image.open(server.current_image)
        st.image(img, use_container_width=True)

    st.divider()

    # PRZYCISK DALEJ (Widoczny tylko dla PRZEGRANEGO z poprzedniej rundy)
    # Zmienna server.who_starts_next została ustawiona w handle_round_win
    
    # Obsługa przypadku "Nikt nie wygrał" (SKIP) - wtedy przycisk widzą obaj lub P1
    allowed_to_click = False
    
    if server.winner_last_round == "NIKT":
        # Jeśli nikt nie wygrał, np. przycisk widzi P1 (żeby gra nie utknęła)
        if st.session_state.my_role == "P1": allowed_to_click = True
        waiting_msg = f"Gospodarz ({server.p1_name}) wznawia grę..."
    else:
        # Normalna zasada: Przegrany zaczyna
        if st.session_state.my_role == server.who_starts_next: allowed_to_click = True
        waiting_msg = f"Czekaj... {server.who_starts_next} rozpoczyna rundę."

    if allowed_to_click:
        st.success("To Ty rozpoczynasz nową rundę! (Jako przegrany lub gospodarz)")
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
            start_new_round()
            st.rerun()
    else:
        st.info(waiting_msg)
        time.sleep(1.5)
        st.rerun()

# RESET W PASKU BOCZNYM
with st.sidebar:
    st.markdown("### Menu")
    if st.button("Reset Gry"):
        reset_full_game()
        st.rerun()


