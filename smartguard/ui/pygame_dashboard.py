"""
Pygame Dashboard for SmartGuard.

A modern, high-contrast dark-mode dashboard displaying:
1. Live Camera Feed with custom state overlays:
   - CRITICAL RULE: Bounding boxes are drawn ONLY for people in STANDING state.
   - For non-standing states (POSSIBLE_FALL, FALLING, FALL_CONFIRMED, DOWN, RECOVERING),
     distinct visual fall markers and alerts are rendered instead.
2. System Status Panel:
   - Camera, Arduino, Firebase, Storage, FPS, Uptime
3. Tracked People Cards:
   - Track ID, Recognized Name, Confidence, Fall State, Torso Angle, Position Zone
4. Recent Alert / Fall Event Banner.
"""

import cv2
import time
import math
import pygame
import numpy as np
from smartguard.state.app_state import AppState
from smartguard.state.person_state import PersonState, FallState, Posture

# Color Palette (Dark Theme)
BG_COLOR = (18, 20, 26)
CARD_BG = (28, 32, 42)
CARD_BORDER = (45, 52, 68)
TEXT_PRIMARY = (240, 243, 248)
TEXT_MUTED = (140, 150, 168)
ACCENT_BLUE = (56, 139, 253)

# State Colors
STATE_COLORS = {
    FallState.NORMAL: (46, 204, 113),         # Emerald Green
    FallState.POSSIBLE_FALL: (241, 196, 15),  # Yellow
    FallState.FALLING: (230, 126, 34),        # Orange
    FallState.FALL_CONFIRMED: (231, 76, 60),  # Bright Red
}

# Posture Colors (for FallState.NORMAL)
POSTURE_COLORS = {
    Posture.UPRIGHT: (46, 204, 113),          # Emerald Green
    Posture.SEATED: (149, 165, 166),          # Slate Gray
    Posture.HORIZONTAL: (149, 165, 166),      # Slate Gray
}


class PygameDashboard:
    def __init__(self, app_state: AppState, config: dict):
        self.app_state = app_state
        self.config = config
        self.ui_cfg = config.get("ui", {})
        self.pose_cfg = config.get("pose", {})

        self.width = self.ui_cfg.get("window_width", 1280)
        self.height = self.ui_cfg.get("window_height", 720)
        self.sidebar_width = self.ui_cfg.get("sidebar_width", 380)
        self.fps_cap = self.ui_cfg.get("fps_cap", 30)

        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("SmartGuard — AI Multi-Person Fall Detection System")

        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 20, bold=True)
        self.font_bold = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 15, bold=True)
        self.font_regular = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 13)
        self.font_small = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 11)
        self.font_alert = pygame.font.SysFont("Segoe UI, Arial, sans-serif", 18, bold=True)

        self.video_rect = pygame.Rect(16, 16, self.width - self.sidebar_width - 32, self.height - 32)
        self.sidebar_rect = pygame.Rect(self.width - self.sidebar_width - 8, 16, self.sidebar_width - 8, self.height - 32)

        self.running = True

    def run(self):
        """Main UI Loop."""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        self.running = False

            self.screen.fill(BG_COLOR)

            # 1. Render Video Feed Area
            self._render_video_feed()

            # 2. Render Sidebar
            self._render_sidebar()

            pygame.display.flip()
            self.clock.tick(self.fps_cap)

        pygame.quit()

    def _render_video_feed(self):
        # Fetch frame and people snapshot from thread-safe state
        frame = None
        people = {}
        with self.app_state.lock:
            if self.app_state.current_frame is not None:
                frame = self.app_state.current_frame.copy()
            people = dict(self.app_state.people)

        v_x, v_y, v_w, v_h = self.video_rect

        if frame is not None:
            # Annotate frame according to the critical state rules
            annotated = self._annotate_frame(frame, people)

            # Resize to fit video_rect
            resized = cv2.resize(annotated, (v_w, v_h))
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            # pygame surfarray expects (width, height, 3) in Fortran order
            surf = pygame.surfarray.make_surface(np.ascontiguousarray(rgb_frame.swapaxes(0, 1)))
            self.screen.blit(surf, (v_x, v_y))
        else:
            # Placeholder when camera isn't ready
            pygame.draw.rect(self.screen, CARD_BG, self.video_rect, border_radius=8)
            placeholder_text = self.font_title.render("WAITING FOR CAMERA SIGNAL...", True, TEXT_MUTED)
            text_rect = placeholder_text.get_rect(center=self.video_rect.center)
            self.screen.blit(placeholder_text, text_rect)

        # Video container border
        has_active_fall = any(p.fall_state in (FallState.FALLING, FallState.FALL_CONFIRMED) for p in people.values())
        border_color = STATE_COLORS[FallState.FALL_CONFIRMED] if (has_active_fall and int(time.time() * 3) % 2 == 0) else CARD_BORDER
        pygame.draw.rect(self.screen, border_color, self.video_rect, width=2, border_radius=8)

        # Video Header Badge
        header_surf = pygame.Surface((220, 32), pygame.SRCALPHA)
        header_surf.fill((18, 20, 26, 200))
        self.screen.blit(header_surf, (v_x + 12, v_y + 12))
        status_dot_color = (46, 204, 113) if frame is not None else (231, 76, 60)
        pygame.draw.circle(self.screen, status_dot_color, (v_x + 24, v_y + 28), 5)
        feed_label = self.font_bold.render("LIVE SURVEILLANCE FEED", True, TEXT_PRIMARY)
        self.screen.blit(feed_label, (v_x + 36, v_y + 20))

    def _annotate_frame(self, frame: np.ndarray, people: dict) -> np.ndarray:
        h, w, _ = frame.shape

        for track_id, person in people.items():
            if not person.bbox:
                continue

            x1, y1, x2, y2 = person.bbox
            color = STATE_COLORS.get(person.fall_state, (255, 255, 255))
            bgr_color = (color[2], color[1], color[0])

            # CRITICAL RULE: UI rendered normally ONLY when FallState is NORMAL
            if person.fall_state == FallState.NORMAL:
                bgr_color = POSTURE_COLORS.get(person.posture, (255, 255, 255))
                bgr_color = (bgr_color[2], bgr_color[1], bgr_color[0])

                if person.posture == Posture.UPRIGHT:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), bgr_color, 2)
                    
                    if person.pose_available and self.pose_cfg.get("draw_landmarks", True):
                        pose_col = (150, 255, 150)
                        def draw_bone(p1, p2):
                            if p1 and p2:
                                cv2.line(frame, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), pose_col, 2)
                        
                        draw_bone(person.left_shoulder, person.right_shoulder)
                        draw_bone(person.left_shoulder, person.left_hip)
                        draw_bone(person.right_shoulder, person.right_hip)
                        draw_bone(person.left_hip, person.right_hip)
                        draw_bone(person.left_hip, person.left_knee)
                        draw_bone(person.right_hip, person.right_knee)
                        draw_bone(person.left_knee, person.left_ankle)
                        draw_bone(person.right_knee, person.right_ankle)
                        
                        for pt in [person.nose, person.left_shoulder, person.right_shoulder,
                                   person.left_hip, person.right_hip, person.left_knee,
                                   person.right_knee, person.left_ankle, person.right_ankle]:
                            if pt:
                                cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, (0, 255, 255), -1)

                    # Label badge above bbox
                    label = f"#{track_id} ({int(person.body_angle)}°)"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(frame, (x1, max(0, y1 - 22)), (x1 + tw + 10, y1), bgr_color, -1)
                    cv2.putText(frame, label, (x1 + 5, max(15, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

                elif person.posture == Posture.SEATED:
                    sit_text = f"Track #{track_id} SITTING"
                    cv2.putText(frame, sit_text, (x1, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, bgr_color, 2, cv2.LINE_AA)

                elif person.posture == Posture.HORIZONTAL:
                    ground_text = f"Track #{track_id} ON GROUND"
                    cv2.putText(frame, ground_text, (x1, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, bgr_color, 2, cv2.LINE_AA)

            elif person.fall_state == FallState.POSSIBLE_FALL:
                # Warning marker: yellow dashed/thin box + caution tag
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 28, bgr_color, 2)
                warning_text = f"POSSIBLE FALL #{track_id} ({int(person.body_angle)}°)"
                cv2.putText(frame, warning_text, (x1, max(20, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, bgr_color, 2, cv2.LINE_AA)

            elif person.fall_state == FallState.POST_FALL_PENDING:
                cx, cy = int(person.center_x), int(person.center_y)
                cv2.drawMarker(frame, (cx, cy), (0, 165, 255), cv2.MARKER_CROSS, 20, 2)
                
                time_lost = time.time() - getattr(person, 'post_fall_timer_start', time.time())
                texts = [
                    f"Track {track_id}",
                    "POST-FALL PENDING",
                    f"Last seen: {time_lost:.1f}s ago",
                    f"Angle: {int(person.body_angle)}°",
                    f"Position: {person.position_zone}"
                ]
                
                by = max(30, y1 - 15)
                for i, text in enumerate(texts):
                    cv2.putText(frame, text, (x1, by + i * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)

            elif person.fall_state in (FallState.FALLING, FallState.FALL_CONFIRMED):
                # Flashing Fall Alert Target
                cx, cy = int(person.center_x), int(person.center_y)
                gx, gy = int(person.ground_x), int(person.ground_y)

                # Ground marker ellipse
                cv2.ellipse(frame, (gx, gy), (int((x2 - x1) / 2), 16), 0, 0, 360, bgr_color, 3)
                # Center crosshair
                cv2.drawMarker(frame, (cx, cy), bgr_color, cv2.MARKER_CROSS, 30, 2)

                # Red Banner over fallen subject
                status_text = f"🚨 FALL CONFIRMED: #{track_id}" if person.fall_state == FallState.FALL_CONFIRMED else f"FALLING: #{track_id}"
                (tw, th), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                bx = max(10, cx - tw // 2)
                by = max(30, y1 - 15)
                cv2.rectangle(frame, (bx - 8, by - th - 8), (bx + tw + 8, by + 6), (0, 0, 180) if person.fall_state == FallState.FALL_CONFIRMED else (0, 100, 255), -1)
                cv2.putText(frame, status_text, (bx, by), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

                # Details text below
                detail_text = f"Angle: {int(person.body_angle)}° | Zone: {person.position_zone}"
                cv2.putText(frame, detail_text, (bx, by + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 255), 1, cv2.LINE_AA)

        return frame

    def _render_sidebar(self):
        s_x, s_y, s_w, s_h = self.sidebar_rect
        summary = self.app_state.get_status_summary()
        people = self.app_state.get_all_people()

        # Background card
        pygame.draw.rect(self.screen, CARD_BG, self.sidebar_rect, border_radius=8)
        pygame.draw.rect(self.screen, CARD_BORDER, self.sidebar_rect, width=1, border_radius=8)

        cur_y = s_y + 16

        # Section: Header
        title = self.font_title.render("SMARTGUARD", True, TEXT_PRIMARY)
        self.screen.blit(title, (s_x + 16, cur_y))
        uptime_str = f"UP: {int(summary['uptime'])}s | FPS: {summary['fps']}"
        fps_lbl = self.font_small.render(uptime_str, True, TEXT_MUTED)
        self.screen.blit(fps_lbl, (s_x + 16, cur_y + 24))
        cur_y += 50

        # Section: System Status Grid
        pygame.draw.line(self.screen, CARD_BORDER, (s_x + 16, cur_y), (s_x + s_w - 16, cur_y))
        cur_y += 12
        sec_lbl = self.font_bold.render("SYSTEM DIAGNOSTICS", True, ACCENT_BLUE)
        self.screen.blit(sec_lbl, (s_x + 16, cur_y))
        cur_y += 24

        indicators = [
            ("Camera", summary["camera"]),
            ("Arduino Serial", summary["arduino"]),
            ("Firebase RTDB", summary["firebase"]),
            ("Cloud Storage", summary["storage"]),
        ]

        for label, is_ok in indicators:
            dot_col = (46, 204, 113) if is_ok else (231, 76, 60)
            pygame.draw.circle(self.screen, dot_col, (s_x + 24, cur_y + 8), 4)
            name_surf = self.font_regular.render(label, True, TEXT_PRIMARY)
            self.screen.blit(name_surf, (s_x + 36, cur_y))

            val_str = "ONLINE" if is_ok else "OFFLINE"
            val_col = (46, 204, 113) if is_ok else (180, 70, 60)
            val_surf = self.font_small.render(val_str, True, val_col)
            self.screen.blit(val_surf, (s_x + s_w - 80, cur_y + 2))
            cur_y += 22

        cur_y += 10
        pygame.draw.line(self.screen, CARD_BORDER, (s_x + 16, cur_y), (s_x + s_w - 16, cur_y))
        cur_y += 12

        # Section: Tracked People
        people_header = f"ACTIVE TRACKS ({len(people)})"
        hdr_surf = self.font_bold.render(people_header, True, ACCENT_BLUE)
        self.screen.blit(hdr_surf, (s_x + 16, cur_y))
        cur_y += 26

        if not people:
            no_people = self.font_regular.render("No subjects currently detected", True, TEXT_MUTED)
            self.screen.blit(no_people, (s_x + 16, cur_y))
            cur_y += 30
        else:
            for track_id, person in list(people.items())[:4]:  # Show top 4 people
                card_h = 74
                card_rect = pygame.Rect(s_x + 12, cur_y, s_w - 24, card_h)
                pygame.draw.rect(self.screen, (22, 25, 33), card_rect, border_radius=6)

                if person.fall_state == FallState.NORMAL:
                    st_col = POSTURE_COLORS.get(person.posture, TEXT_PRIMARY)
                    state_str = person.posture.value
                else:
                    st_col = STATE_COLORS.get(person.fall_state, TEXT_PRIMARY)
                    state_str = person.fall_state.value

                pygame.draw.rect(self.screen, st_col, (s_x + 12, cur_y, 4, card_h), border_top_left_radius=6, border_bottom_left_radius=6)

                # Line 1: Track ID
                name_display = f"Track #{track_id}"
                p_name = self.font_bold.render(name_display, True, TEXT_PRIMARY)
                self.screen.blit(p_name, (s_x + 24, cur_y + 8))

                # State Pill
                state_lbl = self.font_small.render(state_str, True, st_col)
                self.screen.blit(state_lbl, (s_x + s_w - 130, cur_y + 10))

                # Line 2: Torso Angle & Position Zone
                angle_to_show = person.pose_torso_angle if person.pose_available else person.body_angle
                detail = f"Torso Angle: {int(angle_to_show)}° | Zone: {person.position_zone}"
                det_surf = self.font_small.render(detail, True, TEXT_MUTED)
                self.screen.blit(det_surf, (s_x + 24, cur_y + 32))

                # Line 3: Fall Conf
                conf_str = f"Fall Conf: {round(person.fall_confidence, 2)}"
                conf_surf = self.font_small.render(conf_str, True, TEXT_MUTED)
                self.screen.blit(conf_surf, (s_x + 24, cur_y + 50))

                cur_y += card_h + 8

        # Section: Last Fall Event Banner
        cur_y = max(cur_y + 10, s_y + s_h - 110)
        pygame.draw.line(self.screen, CARD_BORDER, (s_x + 16, cur_y), (s_x + s_w - 16, cur_y))
        cur_y += 10

        evt_hdr = self.font_bold.render("LAST DISPATCHED ALERT", True, ACCENT_BLUE)
        self.screen.blit(evt_hdr, (s_x + 16, cur_y))
        cur_y += 22

        last_evt = self.app_state.last_fall_event
        if last_evt:
            evt_text = f"⚠️ Fall Event at {last_evt.get('timestamp', '')[-8:]}"
            e_surf = self.font_regular.render(evt_text, True, STATE_COLORS[FallState.FALL_CONFIRMED])
            self.screen.blit(e_surf, (s_x + 16, cur_y))
            zone_text = f"Zone: {last_evt.get('position_zone')} | Angle: {int(last_evt.get('body_angle', 0))}°"
            z_surf = self.font_small.render(zone_text, True, TEXT_MUTED)
            self.screen.blit(z_surf, (s_x + 16, cur_y + 18))
        else:
            none_surf = self.font_small.render("No fall events dispatched yet", True, TEXT_MUTED)
            self.screen.blit(none_surf, (s_x + 16, cur_y))
