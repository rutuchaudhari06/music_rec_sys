import React, { useState, useEffect, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL;

// Standard Vibe names
const VIBES = [
  "Main Character Energy",
  "Heartbreak & Healing",
  "Late Night Feels",
  "Romantic Yearning",
  "Chaotic Energy",
  "Escapism & Discovery",
  "Peaceful & Hopeful"
];

export default function App() {
  // Screen state
  const [currentScreen, setCurrentScreen] = useState('WELCOME'); // WELCOME, LOGIN, SIGNUP, ONBOARDING_SEARCH, HOME_MENU, ENTER_MOOD, VIBE_PREVIEW, RECOMMENDATIONS, PLAYER, EXPORT_PLAYLIST
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [userEmail, setUserEmail] = useState('');

  // Lists & scrolling navigation
  const [menuIndex, setMenuIndex] = useState(0);

  // Authentication forms
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');

  // Onboarding Seed Selection
  const [seedQuery, setSeedQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedSeeds, setSelectedSeeds] = useState([]);

  // Mood input & Vibe details
  const [moodText, setMoodText] = useState('');
  const [detectedVibe, setDetectedVibe] = useState('Peaceful & Hopeful');
  const [vibeCoords, setVibeCoords] = useState({ valence: 0.5, arousal: 0.4 });
  const [vibeOverride, setVibeOverride] = useState('');

  // Recommendations and Player
  const [recommendations, setRecommendations] = useState([]);
  const [activeTrackIndex, setActiveTrackIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progressPercent, setProgressPercent] = useState(0);
  const [likedStatus, setLikedStatus] = useState(false); // Visual heart indicator

  // Spotify status & exports
  const [spotifyConnected, setSpotifyConnected] = useState(false);
  const [playlistName, setPlaylistName] = useState('');

  // Status popup modal overlays
  const [statusTitle, setStatusTitle] = useState('');
  const [statusDetail, setStatusDetail] = useState('');
  const [showStatus, setShowStatus] = useState(false);

  // Rotary click-wheel drag refs
  const wheelRef = useRef(null);
  const startAngleRef = useRef(0);
  const angleAccumulatorRef = useRef(0);
  const isRotatingRef = useRef(false);

  // Virtual player interval
  const playerIntervalRef = useRef(null);

  // Focus element helper for forms
  const [focusedFormIndex, setFocusedFormIndex] = useState(0); // 0 = Email, 1 = Password, 2 = Submit Button

  // 1. Initial Authentication & Status Check
  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      fetchUserProfile();
    } else {
      localStorage.removeItem('token');
      setCurrentScreen('WELCOME');
    }
  }, [token]);

  const fetchUserProfile = async () => {
    try {
      setLoading(true);

      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();

        setUserEmail(data.email);
        checkSpotifyStatus();

        if (data.onboarding_completed) {
          setCurrentScreen("HOME_MENU");
        } else {
          setCurrentScreen("ONBOARDING_SEARCH");
        }
      } else {
        setToken("");
      }
    } catch (err) {
      console.error(err);   // <-- add this
      showPopup("Network Error", "Could not connect to the backend server.");
      setToken("");
    } finally {
      setLoading(false);
    }
  };

  const checkSpotifyStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/spotify/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
    const data = await res.json();

    setSpotifyConnected(data.connected);

    if (data.connected && pendingExport) {
        setPendingExport(false);
        exportPlaylist();
    }
}
    } catch (err) {
      console.error("Spotify status check failed", err);
    }
  };

  // Helper popup
  const showPopup = (title, detail) => {
    setStatusTitle(title);
    setStatusDetail(detail);
    setShowStatus(true);
    setTimeout(() => {
      setShowStatus(false);
    }, 4000);
  };

  // 2. Authentication handlers
  const handleSignup = async () => {
    if (!emailInput || !passwordInput) {
      showPopup("Validation Error", "Please fill in all credentials fields.");
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput, password: passwordInput })
      });
      const data = await res.json();
      if (res.ok) {
        showPopup("Signup Success", "Account created successfully. Logging you in...");
        handleLogin();
      } else {
        showPopup("Signup Failed", data.detail || "Account registration failed.");
      }
    } catch (err) {
      showPopup("Network Error", "Signup endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!emailInput || !passwordInput) {
      showPopup("Validation Error", "Please fill in email and password.");
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput, password: passwordInput })
      });
      const data = await res.json();
      if (res.ok) {
        setToken(data.access_token);
        setEmailInput('');
        setPasswordInput('');
      } else {
        showPopup("Login Failed", data.detail || "Invalid login credentials.");
      }
    } catch (err) {
      showPopup("Network Error", "Login endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setToken('');
    setUserEmail('');
    setRecommendations([]);
    setSelectedSeeds([]);
    setSearchResults([]);
    setSpotifyConnected(false);
    setCurrentScreen('WELCOME');
  };

  // 3. Onboarding Seed selection handlers
  const handleSeedSearch = async () => {
    if (seedQuery.trim().length < 2) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/songs/search?query=${encodeURIComponent(seedQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
        setMenuIndex(0); // Reset select index to top
      }
    } catch (err) {
      showPopup("Search Failed", "Could not fetch songs from static library.");
    } finally {
      setLoading(false);
    }
  };

  const toggleSeedSelect = (track) => {
    if (selectedSeeds.some(s => s.track_id === track.track_id)) {
      setSelectedSeeds(selectedSeeds.filter(s => s.track_id !== track.track_id));
    } else {
      setSelectedSeeds([...selectedSeeds, track]);
    }
  };

  const submitSeeds = async () => {
    if (selectedSeeds.length < 3) {
      showPopup("Onboarding Error", "Please select at least 3 initial songs to seed your preferences.");
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/recommendations/seed`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ seed_track_ids: selectedSeeds.map(s => s.track_id) })
      });
      if (res.ok) {
        showPopup("Preferences Set", "Seeds registered! Welcome to Twirl.");
        setCurrentScreen('HOME_MENU');
        setMenuIndex(0);
      } else {
        const data = await res.json();
        showPopup("Registration Failed", data.detail || "Onboarding seed submission failed.");
      }
    } catch (err) {
      showPopup("Network Error", "Seed endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

  // 4. Recommendation pipeline handlers
  const getDetectedEmotion = async () => {
    if (!moodText.trim()) {
      showPopup("Input Missing", "Please express how you feel in 2-3 sentences.");
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/emotion/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: moodText })
      });
      if (res.ok) {
        const data = await res.json();
        setDetectedVibe(data.dominant_vibe);
        setVibeCoords({ valence: data.target_valence, arousal: data.target_arousal });
        setVibeOverride('');
        setCurrentScreen('VIBE_PREVIEW');
        setMenuIndex(0);
      } else {
        showPopup("Prediction Failed", "Error classifying input mood text.");
      }
    } catch (err) {
      showPopup("Network Error", "Emotion endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

  const fetchRecommendations = async (overrideVibe = '') => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/recommendations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          text: moodText,
          vibe_override: overrideVibe || null,
          limit: 20
        })
      });
      if (res.ok) {
        const data = await res.json();
        setRecommendations(data.recommendations);
        if (data.recommendations.length > 0) {
          setActiveTrackIndex(0);
          setCurrentScreen('RECOMMENDATIONS');
          setMenuIndex(0);
        } else {
          showPopup("No Tracks Found", "Try typing a different mood prompt.");
        }
      } else {
        const data = await res.json();
        showPopup("Recommender Failed", data.detail || "Could not generate recommendations.");
      }
    } catch (err) {
      showPopup("Network Error", "Recommendations endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

  // 5. Interaction logging (like/dislike/skip)
  const logInteraction = async (trackId, type) => {
    try {
      const res = await fetch(`${API_BASE}/api/interactions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ track_id: trackId, interaction_type: type })
      });
      if (res.ok) {
        const data = await res.json();
        console.log(`Log interaction ${type} successful`, data);
      }
    } catch (err) {
      console.error("Failed to log interaction on server", err);
    }
  };

  // 6. Spotify connection & export playlist
  const handleSpotifyConnect = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/spotify/connect`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();

      if (!res.ok) {
        showPopup("Spotify Connect Failed", data.detail || "Could not start Spotify connection.");
        return;
      }

      const width = 500;
      const height = 600;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        data.auth_url,
        "SpotifyConnect",
        `width=${width},height=${height},left=${left},top=${top}`
      );

      if (!popup) {
        showPopup("Popup Blocked", "Please allow popups to connect Spotify.");
        return;
      }

      const timer = setInterval(() => {
        if (popup.closed) {
          clearInterval(timer);
          checkSpotifyStatus();
          showPopup("Spotify Status", "Sync connection refreshed.");
        }
      }, 1000);
    } catch (err) {
      showPopup("Network Error", "Spotify connection endpoint unreachable.");
    } finally {
      setLoading(false);
    }
  };

const exportPlaylist = async () => {
    const finalName = playlistName.trim() || `Twirl: ${vibeOverride || detectedVibe}`;
    if (recommendations.length === 0) {
      showPopup("Export Error", "No recommendations available to export.");
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/spotify/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          playlist_name: finalName,
          track_ids: recommendations.map(r => r.track_id)
        })
      });
      if (res.ok) {
        const data = await res.json();
        showPopup("Export Successful!", `Playlist created on Spotify: "${finalName}"`);
        setCurrentScreen('RECOMMENDATIONS');
        setPlaylistName('');
      } else {
        const data = await res.json();
        showPopup("Export Failed", data.detail || "Failed to create playlist.");
      }
    } catch (err) {
      showPopup("Network Error", "Spotify export endpoint unreachable.");
    } finally {
      setLoading(false);
    }
};

  const handleExportPlaylist = async () => {

    if (!spotifyConnected) {
      setPendingExport(true);
      handleSpotifyConnect();
      return;
    }
    exportPlaylist();
    
  };

  // 7. Virtual Audio Player logic
  useEffect(() => {
    if (isPlaying) {
      playerIntervalRef.current = setInterval(() => {
        setProgressPercent(prev => {
          if (prev >= 100) {
            // Track finished, trigger auto-skip (Skip log and load next track)
            handlePlayerForward(true); // Auto skip
            return 0;
          }
          return prev + 2;
        });
      }, 1000);
    } else {
      clearInterval(playerIntervalRef.current);
    }
    return () => clearInterval(playerIntervalRef.current);
  }, [isPlaying, activeTrackIndex, recommendations]);

  const handlePlayerPlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handlePlayerForward = (isAuto = false) => {
    if (recommendations.length === 0) return;
    const currentTrack = recommendations[activeTrackIndex];

    // Log skip interaction (only if user explicitly skips or it finished and we record it as skip)
    logInteraction(currentTrack.track_id, "skip");

    setIsPlaying(false);
    setProgressPercent(0);
    setLikedStatus(false);

    if (activeTrackIndex < recommendations.length - 1) {
      setActiveTrackIndex(activeTrackIndex + 1);
      setIsPlaying(true);
    } else {
      showPopup("Playlist End", "You've listened to all recommended tracks.");
      setCurrentScreen('RECOMMENDATIONS');
    }
  };

  const handlePlayerBackward = () => {
    // Dislike current track, remove it, update vector, and load next
    if (recommendations.length === 0) return;
    const currentTrack = recommendations[activeTrackIndex];

    // Log dislike/remove interaction
    logInteraction(currentTrack.track_id, "dislike");

    setIsPlaying(false);
    setProgressPercent(0);
    setLikedStatus(false);
    showPopup("Track Removed", "Dislike recorded. Refining recommendation vector...");

    // Remove the track from active recommendations list
    const updatedRecs = recommendations.filter((_, idx) => idx !== activeTrackIndex);
    setRecommendations(updatedRecs);

    if (updatedRecs.length > 0) {
      // Keep same index if within bounds, otherwise wrap to start
      const nextIdx = activeTrackIndex >= updatedRecs.length ? 0 : activeTrackIndex;
      setActiveTrackIndex(nextIdx);
      setIsPlaying(true);
    } else {
      setCurrentScreen('HOME_MENU');
    }
  };

  const handlePlayerLike = () => {
    if (recommendations.length === 0) return;
    const currentTrack = recommendations[activeTrackIndex];

    logInteraction(currentTrack.track_id, "like");
    setLikedStatus(true);
    showPopup("Loved Track!", "Added to preferences (+1 Love weight)");
  };

  // 8. click-wheel gesture rotation scroll mapping
  const handleWheelMouseDown = (e) => {
    if (!wheelRef.current) return;
    isRotatingRef.current = true;
    const rect = wheelRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const clientX = e.clientX || (e.touches && e.touches[0].clientX);
    const clientY = e.clientY || (e.touches && e.touches[0].clientY);

    const x = clientX - centerX;
    const y = clientY - centerY;

    startAngleRef.current = Math.atan2(y, x);
    angleAccumulatorRef.current = 0;
  };

  const handleWheelMouseMove = (e) => {
    if (!isRotatingRef.current || !wheelRef.current) return;
    const rect = wheelRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const clientX = e.clientX || (e.touches && e.touches[0].clientX);
    const clientY = e.clientY || (e.touches && e.touches[0].clientY);

    const x = clientX - centerX;
    const y = clientY - centerY;

    const currentAngle = Math.atan2(y, x);
    let delta = currentAngle - startAngleRef.current;

    // Handle wrap around jump
    if (delta > Math.PI) delta -= 2 * Math.PI;
    if (delta < -Math.PI) delta += 2 * Math.PI;

    // Sensitivity threshold (rad)
    const threshold = 0.22;
    angleAccumulatorRef.current += delta;

    if (Math.abs(angleAccumulatorRef.current) >= threshold) {
      const direction = angleAccumulatorRef.current > 0 ? 1 : -1;
      triggerWheelScroll(direction);
      angleAccumulatorRef.current = 0; // reset
    }

    startAngleRef.current = currentAngle;
  };

  const handleWheelMouseUp = () => {
    isRotatingRef.current = false;
  };

  const getListLengthForScreen = (screen) => {
    switch (screen) {
      case 'WELCOME':
        return 2;
      case 'LOGIN':
      case 'SIGNUP':
        return 3; // Email input, Password input, Submit button
      case 'HOME_MENU':
        return 4; // Enter Mood, Spotify Connect, Onboarding, Logout
      case 'ONBOARDING_SEARCH':
        return searchResults.length;
      case 'VIBE_PREVIEW':
        return 8; // Use Detected Vibe + 7 overrides
      case 'RECOMMENDATIONS':
        return recommendations.length + 1; // Tracks list + "Export Playlist to Spotify" item
      case 'EXPORT_PLAYLIST':
        return 2; // Playlist name input, Export button
      default:
        return 0;
    }
  };

  const triggerWheelScroll = (direction) => {
    const listLen = getListLengthForScreen(currentScreen);
    if (listLen <= 0) return;

    if (currentScreen === 'LOGIN' || currentScreen === 'SIGNUP') {
      setFocusedFormIndex(prev => {
        let next = prev + direction;
        if (next < 0) next = 2;
        if (next > 2) next = 0;
        return next;
      });
    } else if (currentScreen === 'EXPORT_PLAYLIST') {
      setFocusedFormIndex(prev => {
        let next = prev + direction;
        if (next < 0) next = 1;
        if (next > 1) next = 0;
        return next;
      });
    } else {
      setMenuIndex(prev => {
        let next = prev + direction;
        if (next < 0) next = listLen - 1;
        if (next >= listLen) next = 0;
        return next;
      });
    }
  };

  // 9. Click-wheel button triggers (Select, Menu, Forward, Backward)
  const handleSelectClick = () => {
    switch (currentScreen) {
      case 'WELCOME':
        if (menuIndex === 0) {
          setCurrentScreen('LOGIN');
          setFocusedFormIndex(0);
        } else {
          setCurrentScreen('SIGNUP');
          setFocusedFormIndex(0);
        }
        break;
      case 'LOGIN':
        if (focusedFormIndex === 0) {
          document.getElementById('login-email')?.focus();
        } else if (focusedFormIndex === 1) {
          document.getElementById('login-password')?.focus();
        } else {
          handleLogin();
        }
        break;
      case 'SIGNUP':
        if (focusedFormIndex === 0) {
          document.getElementById('signup-email')?.focus();
        } else if (focusedFormIndex === 1) {
          document.getElementById('signup-password')?.focus();
        } else {
          handleSignup();
        }
        break;
      case 'HOME_MENU':
        if (menuIndex === 0) {
          setCurrentScreen('ENTER_MOOD');
        } else if (menuIndex === 1) {
          if (!spotifyConnected) {
            handleSpotifyConnect();
          } else {
            showPopup("Spotify Status", `Linked account: ${userEmail}`);
          }
        } else if (menuIndex === 2) {
          setCurrentScreen('ONBOARDING_SEARCH');
          setSelectedSeeds([]);
          setSearchResults([]);
          setMenuIndex(0);
        } else if (menuIndex === 3) {
          handleLogout();
        }
        break;
      case 'ONBOARDING_SEARCH':
        if (searchResults.length > 0 && searchResults[menuIndex]) {
          toggleSeedSelect(searchResults[menuIndex]);
        }
        break;
      case 'VIBE_PREVIEW':
        if (menuIndex === 0) {
          // Confirm detected vibe coordinates
          fetchRecommendations();
        } else {
          // Vibe override select
          const selectedOverride = VIBES[menuIndex - 1];
          setVibeOverride(selectedOverride);
          fetchRecommendations(selectedOverride);
        }
        break;
      case 'RECOMMENDATIONS':
        if (menuIndex === recommendations.length) {
          // Export playlist item
          setCurrentScreen('EXPORT_PLAYLIST');
          setPlaylistName(`Twirl: ${vibeOverride || detectedVibe}`);
          setFocusedFormIndex(0);
        } else {
          // Selected a song from recommendations list to play
          setActiveTrackIndex(menuIndex);
          setCurrentScreen('PLAYER');
          setIsPlaying(true);
          setProgressPercent(0);
          setLikedStatus(false);
        }
        break;
      case 'PLAYER':
        // Liked status interaction in player
        handlePlayerLike();
        break;
      case 'EXPORT_PLAYLIST':
        if (focusedFormIndex === 0) {
          document.getElementById('playlist-name-input')?.focus();
        } else {
          handleExportPlaylist();
        }
        break;
      default:
        break;
    }
  };

  const handleMenuClick = () => {
    // Acts as back button
    switch (currentScreen) {
      case 'LOGIN':
      case 'SIGNUP':
        setCurrentScreen('WELCOME');
        setMenuIndex(0);
        break;
      case 'ONBOARDING_SEARCH':
        if (token) {
          setCurrentScreen('HOME_MENU');
        } else {
          setCurrentScreen('WELCOME');
        }
        setMenuIndex(0);
        break;
      case 'ENTER_MOOD':
        setCurrentScreen('HOME_MENU');
        setMenuIndex(0);
        break;
      case 'VIBE_PREVIEW':
        setCurrentScreen('ENTER_MOOD');
        break;
      case 'RECOMMENDATIONS':
        setCurrentScreen('HOME_MENU');
        setMenuIndex(0);
        break;
      case 'PLAYER':
        setCurrentScreen('RECOMMENDATIONS');
        setIsPlaying(false);
        setMenuIndex(activeTrackIndex);
        break;
      case 'EXPORT_PLAYLIST':
        setCurrentScreen('RECOMMENDATIONS');
        setMenuIndex(recommendations.length);
        break;
      default:
        break;
    }
  };

  // Keyboard shortcut fallback for testing
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowUp') {
        triggerWheelScroll(-1);
      } else if (e.key === 'ArrowDown') {
        triggerWheelScroll(1);
      } else if (e.key === 'Enter') {
        handleSelectClick();
      } else if (e.key === 'Escape') {
        handleMenuClick();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentScreen, menuIndex, focusedFormIndex, searchResults, recommendations, activeTrackIndex, moodText, selectedSeeds, playlistName]);

  const [pendingExport, setPendingExport] = useState(false);


  return (
    <div className="ipod-container">
      {/* iPod top jacks */}
      <div className="ipod-hold-switch"></div>
      <div className="headphone-jack"></div>

      {/* Screen Bezel */}
      <div className="ipod-screen-bezel">
        <div className="ipod-screen">
          {/* Status Bar */}
          <div className="screen-header">
            <span>{isPlaying ? "► Playing" : "|| Paused"}</span>
            <span style={{ fontWeight: 'bold' }}>Twirl</span>
            <span>[===]</span>
          </div>

          {/* Screen Content Switcher */}
          <div className="screen-content">

            {/* Status Modal Overlay */}
            {showStatus && (
              <div className="screen-overlay">
                <div className="screen-overlay-title">{statusTitle}</div>
                <div className="screen-overlay-text">{statusDetail}</div>
              </div>
            )}

            {/* Spinner Overlay */}
            {loading && (
              <div className="screen-overlay" style={{ zIndex: 90 }}>
                <div className="screen-overlay-title">Processing...</div>
                <div className="retro-loading-bar">
                  <div className="retro-loading-fill"></div>
                </div>
              </div>
            )}

            {/* Screen 1: WELCOME SCREEN */}
            {currentScreen === 'WELCOME' && (
              <ul className="retro-list">
                <li style={{ padding: '8px', fontSize: '14px', fontWeight: 'bold', borderBottom: '1.5px solid var(--screen-text)', textAlign: 'center' }}>
                  Twirl iPod
                </li>
                <li className={`retro-item ${menuIndex === 0 ? 'selected' : ''}`} onClick={() => { setMenuIndex(0); setCurrentScreen('LOGIN'); }}>
                  <span>Login</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                <li className={`retro-item ${menuIndex === 1 ? 'selected' : ''}`} onClick={() => { setMenuIndex(1); setCurrentScreen('SIGNUP'); }}>
                  <span>Register</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                <li style={{ padding: '16px 8px', fontSize: '9.5px', textAlign: 'center', opacity: 0.85, lineHeight: 1.3 }}>
                  Spin click-wheel to select. Center button to confirm. Menu to go back.
                </li>
              </ul>
            )}

            {/* Screen 2: LOGIN SCREEN */}
            {currentScreen === 'LOGIN' && (
              <div className="retro-form">
                <h2>iPod Account Login</h2>
                <div className="retro-form-field">
                  <span className="retro-label">EMAIL:</span>
                  <input
                    id="login-email"
                    type="email"
                    className="retro-input"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    style={{ border: focusedFormIndex === 0 ? '2px solid black' : '1.5px solid var(--screen-text)' }}
                    placeholder="name@email.com"
                  />
                </div>
                <div className="retro-form-field">
                  <span className="retro-label">PASSWORD:</span>
                  <input
                    id="login-password"
                    type="password"
                    className="retro-input"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    style={{ border: focusedFormIndex === 1 ? '2px solid black' : '1.5px solid var(--screen-text)' }}
                    placeholder="******"
                  />
                </div>
                <div
                  className={`retro-item ${focusedFormIndex === 2 ? 'selected' : ''}`}
                  onClick={handleLogin}
                  style={{ justifyContent: 'center', fontWeight: 'bold', border: '1.5px solid var(--screen-text)', marginTop: '8px', padding: '4px' }}
                >
                  Confirm Login
                </div>
                <div className="retro-hint">MENU returns to welcome</div>
              </div>
            )}

            {/* Screen 3: SIGNUP SCREEN */}
            {currentScreen === 'SIGNUP' && (
              <div className="retro-form">
                <h2>Create Account</h2>
                <div className="retro-form-field">
                  <span className="retro-label">EMAIL:</span>
                  <input
                    id="signup-email"
                    type="email"
                    className="retro-input"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    style={{ border: focusedFormIndex === 0 ? '2px solid black' : '1.5px solid var(--screen-text)' }}
                    placeholder="name@email.com"
                  />
                </div>
                <div className="retro-form-field">
                  <span className="retro-label">PASSWORD:</span>
                  <input
                    id="signup-password"
                    type="password"
                    className="retro-input"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    style={{ border: focusedFormIndex === 1 ? '2px solid black' : '1.5px solid var(--screen-text)' }}
                    placeholder="******"
                  />
                </div>
                <div
                  className={`retro-item ${focusedFormIndex === 2 ? 'selected' : ''}`}
                  onClick={handleSignup}
                  style={{ justifyContent: 'center', fontWeight: 'bold', border: '1.5px solid var(--screen-text)', marginTop: '8px', padding: '4px' }}
                >
                  Create Profile
                </div>
                <div className="retro-hint">MENU returns to welcome</div>
              </div>
            )}

            {/* Screen 4: ONBOARDING SEED SEARCH & SELECT */}
            {currentScreen === 'ONBOARDING_SEARCH' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--screen-text)', fontSize: '11px', display: 'flex', gap: '4px' }}>
                  <input
                    type="text"
                    className="retro-input"
                    style={{ flex: 1, padding: '2px 4px', fontSize: '10px' }}
                    value={seedQuery}
                    onChange={(e) => setSeedQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSeedSearch()}
                    placeholder="Search seed songs..."
                  />
                  <button
                    onClick={handleSeedSearch}
                    style={{ background: 'transparent', border: '1px solid var(--screen-text)', fontSize: '10px', color: 'var(--screen-text)', cursor: 'pointer' }}
                  >
                    Go
                  </button>
                </div>

                {/* Search Result Tracks */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  {searchResults.length === 0 ? (
                    <div style={{ padding: '20px 10px', textAlign: 'center', fontSize: '11px' }}>
                      Search above & select 3 seed tracks to seed preference Rocchio vector.
                      {selectedSeeds.length > 0 && (
                        <div style={{ marginTop: '10px', fontWeight: 'bold' }}>
                          Seeds selected: {selectedSeeds.length}
                        </div>
                      )}
                    </div>
                  ) : (
                    <ul className="retro-list">
                      {searchResults.map((track, idx) => {
                        const isChosen = selectedSeeds.some(s => s.track_id === track.track_id);
                        return (
                          <li
                            key={track.track_id}
                            className={`retro-item ${menuIndex === idx ? 'selected' : ''}`}
                            onClick={() => toggleSeedSelect(track)}
                            style={{ padding: '4px 8px' }}
                          >
                            <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '85%' }}>
                              <span style={{ fontWeight: 'bold', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {track.track_name}
                              </span>
                              <span style={{ fontSize: '9px', opacity: 0.8 }}>
                                {track.artists}
                              </span>
                            </div>
                            <span style={{ fontSize: '12px' }}>{isChosen ? "★" : "☆"}</span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                {/* Fixed Footer with selections check */}
                <div
                  onClick={selectedSeeds.length >= 3 ? submitSeeds : undefined}
                  style={{
                    padding: '6px 8px',
                    borderTop: '1.5px solid var(--screen-text)',
                    fontSize: '11px',
                    textAlign: 'center',
                    fontWeight: 'bold',
                    backgroundColor: selectedSeeds.length >= 3 ? 'rgba(0,0,0,0.1)' : 'transparent',
                    cursor: selectedSeeds.length >= 3 ? 'pointer' : 'default'
                  }}
                >
                  {selectedSeeds.length >= 3 ? "► SUBMIT SEEDS NOW" : `Seeds chosen: ${selectedSeeds.length}/3`}
                </div>
              </div>
            )}

            {/* Screen 5: HOME MENU */}
            {currentScreen === 'HOME_MENU' && (
              <ul className="retro-list">
                <li style={{ padding: '6px 8px', fontSize: '13px', fontWeight: 'bold', borderBottom: '1.5px solid var(--screen-text)', display: 'flex', justifyContent: 'space-between' }}>
                  <span>Main Menu</span>
                  <span style={{ fontSize: '10px' }}>{userEmail.split('@')[0]}</span>
                </li>
                <li className={`retro-item ${menuIndex === 0 ? 'selected' : ''}`} onClick={() => setCurrentScreen('ENTER_MOOD')}>
                  <span>Enter Mood</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                <li className={`retro-item ${menuIndex === 1 ? 'selected' : ''}`} onClick={handleSpotifyConnect}>
                  <span>Spotify: {spotifyConnected ? "Connected" : "Link Account"}</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                <li className={`retro-item ${menuIndex === 2 ? 'selected' : ''}`} onClick={() => { setCurrentScreen('ONBOARDING_SEARCH'); setSearchResults([]); setSelectedSeeds([]); }}>
                  <span>Onboarding Seeds</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                <li className={`retro-item ${menuIndex === 3 ? 'selected' : ''}`} onClick={handleLogout}>
                  <span>Logout</span>
                  <span className="retro-item-arrow">►</span>
                </li>
              </ul>
            )}

            {/* Screen 6: ENTER MOOD SCREEN */}
            {currentScreen === 'ENTER_MOOD' && (
              <div className="retro-form">
                <h2>Describe Your Vibe</h2>
                <textarea
                  className="retro-textarea"
                  value={moodText}
                  onChange={(e) => setMoodText(e.target.value)}
                  placeholder="Type 2-3 sentences here. E.g. 'I had a really busy day at work. Now I just want to sit back, relax, and listen to some chilled out acoustic beats.'"
                />
                <div
                  className="retro-item selected"
                  onClick={getDetectedEmotion}
                  style={{ justifyContent: 'center', fontWeight: 'bold', border: '1.5px solid var(--screen-text)', marginTop: '8px', padding: '4px', textAlign: 'center' }}
                >
                  Analyze Emotion
                </div>
                <div className="retro-hint">MENU returns to home</div>
              </div>
            )}

            {/* Screen 7: VIBE PREVIEW & OVERRIDE */}
            {currentScreen === 'VIBE_PREVIEW' && (
              <ul className="retro-list">
                <li style={{ padding: '6px 8px', borderBottom: '1.5px solid var(--screen-text)', fontSize: '11px', textAlign: 'center', fontWeight: 'bold', lineHeight: 1.3 }}>
                  Detected Vibe:<br />"{detectedVibe}"
                </li>
                <li className={`retro-item ${menuIndex === 0 ? 'selected' : ''}`} onClick={() => fetchRecommendations()}>
                  <span style={{ fontWeight: 'bold' }}>Confirm & Recommendations</span>
                  <span className="retro-item-arrow">►</span>
                </li>
                {VIBES.map((v, idx) => (
                  <li
                    key={v}
                    className={`retro-item ${menuIndex === idx + 1 ? 'selected' : ''}`}
                    onClick={() => { setVibeOverride(v); fetchRecommendations(v); }}
                  >
                    <span>Override: {v}</span>
                    <span className="retro-item-arrow">►</span>
                  </li>
                ))}
              </ul>
            )}

            {/* Screen 8: RECOMMENDATIONS TRACKLIST */}
            {currentScreen === 'RECOMMENDATIONS' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ padding: '5px 8px', borderBottom: '1px solid var(--screen-text)', fontSize: '11px', fontWeight: 'bold', textAlign: 'center' }}>
                  {vibeOverride || detectedVibe} Recs ({recommendations.length})
                </div>

                <div style={{ flex: 1, overflowY: 'auto' }}>
                  <ul className="retro-list">
                    {recommendations.map((track, idx) => (
                      <li
                        key={track.track_id}
                        className={`retro-item ${menuIndex === idx ? 'selected' : ''}`}
                        onClick={() => {
                          setActiveTrackIndex(idx);
                          setCurrentScreen('PLAYER');
                          setIsPlaying(true);
                          setProgressPercent(0);
                        }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '85%' }}>
                          <span style={{ fontWeight: 'bold', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {idx + 1}. {track.track_name}
                          </span>
                          <span style={{ fontSize: '9px', opacity: 0.8 }}>
                            {track.artists}
                          </span>
                        </div>
                        <span style={{ fontSize: '10px' }}>►</span>
                      </li>
                    ))}

                    {/* Spotify export shortcut at the bottom of the list */}
                    <li
                      className={`retro-item ${menuIndex === recommendations.length ? 'selected' : ''}`}
                      onClick={() => setCurrentScreen('EXPORT_PLAYLIST')}
                      style={{ borderTop: '1.5px solid var(--screen-text)', padding: '6px 8px', backgroundColor: 'rgba(0,0,0,0.05)' }}
                    >
                      <span style={{ fontWeight: 'bold' }}>Export Playlist to Spotify</span>
                      <span className="retro-item-arrow">►</span>
                    </li>
                  </ul>
                </div>
              </div>
            )}

            {/* Screen 9: NOW PLAYING DECK / PLAYER */}
            {currentScreen === 'PLAYER' && recommendations[activeTrackIndex] && (
              <div className="now-playing-container">
                <div className="now-playing-info">
                  <span style={{ fontSize: '9.5px', textTransform: 'uppercase', letterSpacing: '0.5px', opacity: 0.8, marginBottom: '4px' }}>
                    Now Playing ({activeTrackIndex + 1}/{recommendations.length})
                  </span>
                  <div className="now-playing-title">
                    {recommendations[activeTrackIndex].track_name}
                  </div>
                  <div className="now-playing-artist">
                    {recommendations[activeTrackIndex].artists}
                  </div>
                  <div className="now-playing-album">
                    {recommendations[activeTrackIndex].album_name}
                  </div>

                  {likedStatus && (
                    <div style={{ fontSize: '14px', color: '#cc0000', marginTop: '4px', fontWeight: 'bold' }}>
                      ♥ LIKED
                    </div>
                  )}
                </div>

                <div style={{ width: '100%' }}>
                  <div className="progress-bar-container">
                    <span>0:{(progressPercent * 0.03).toFixed(0).padStart(2, '0')}</span>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${progressPercent}%` }}></div>
                    </div>
                    <span>3:00</span>
                  </div>

                  <div className="now-playing-controls-hints">
                    <span>Center: ♥ Like</span>
                    <span>►|| Play</span>
                    <span>►►| Skip</span>
                  </div>
                </div>
              </div>
            )}

            {/* Screen 10: EXPORT PLAYLIST SCREEN */}
            {currentScreen === 'EXPORT_PLAYLIST' && (
              <div className="retro-form">
                <h2>Export to Spotify</h2>
                <div className="retro-form-field">
                  <span className="retro-label">PLAYLIST NAME:</span>
                  <input
                    id="playlist-name-input"
                    type="text"
                    className="retro-input"
                    value={playlistName}
                    onChange={(e) => setPlaylistName(e.target.value)}
                    style={{ border: focusedFormIndex === 0 ? '2px solid black' : '1.5px solid var(--screen-text)' }}
                  />
                </div>

                <div
                  className={`retro-item ${focusedFormIndex === 1 ? 'selected' : ''}`}
                  onClick={handleExportPlaylist}
                  style={{ justifyContent: 'center', fontWeight: 'bold', border: '1.5px solid var(--screen-text)', marginTop: '8px', padding: '4px', textAlign: 'center' }}
                >
                  Create & Export
                </div>
                <div className="retro-hint">
                  {spotifyConnected
                    ? "Ready to export!"
                    : "Spotify isn't connected. Clicking Export will connect it first."}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Physical click-wheel */}
      <div
        className="click-wheel-container"
        ref={wheelRef}
        onMouseDown={handleWheelMouseDown}
        onMouseMove={handleWheelMouseMove}
        onMouseUp={handleWheelMouseUp}
        onMouseLeave={handleWheelMouseUp}
        onTouchStart={handleWheelMouseDown}
        onTouchMove={handleWheelMouseMove}
        onTouchEnd={handleWheelMouseUp}
      >
        <button className="wheel-btn menu" onClick={handleMenuClick}>MENU</button>
        <button className="wheel-btn next" onClick={() => {
          if (currentScreen === 'PLAYER') {
            handlePlayerForward();
          } else {
            triggerWheelScroll(1);
          }
        }}>▶▶|</button>
        <button className="wheel-btn prev" onClick={() => {
          if (currentScreen === 'PLAYER') {
            handlePlayerBackward();
          } else {
            triggerWheelScroll(-1);
          }
        }}>|◀◀</button>
        <button className="wheel-btn playpause" onClick={() => {
          if (currentScreen === 'PLAYER') {
            handlePlayerPlayPause();
          } else {
            handleSelectClick(); // center action fallback
          }
        }}>▶||</button>

        {/* Center select button */}
        <button className="select-button" onClick={handleSelectClick}></button>
      </div>
    </div>
  );
}
