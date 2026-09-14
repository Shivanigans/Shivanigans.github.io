class Page extends DCLogic {
  state = { scale: 1, wide: false, lang: 'en', guidesOpen: false, officeState: 'Delhi', panelOpen: false, loggedIn: false, loginOpen: true, sirState: 'Madhya Pradesh', sirDismissed: false };

  // PLACEHOLDER DATA — check against the ECI site before use. Phase dates, the list of
  // states currently mid-phase, and the documents accepted under Special Intensive Revision
  // are all unconfirmed. The nationwide exercise was announced on 27 October 2025.
  sirPhases = {
    'Madhya Pradesh': { open: true, closes: '30 September 2026' },
    'Delhi': { open: true, closes: '7 October 2026' },
    'Maharashtra': { open: false, closes: '' },
    'Karnataka': { open: false, closes: '' },
    'Tamil Nadu': { open: false, closes: '' },
    'Uttar Pradesh': { open: true, closes: '15 October 2026' },
    'West Bengal': { open: false, closes: '' }
  };

  offices = {
    'Delhi': { name: 'Chief Electoral Officer, Delhi', address: 'Old St. Stephen\u2019s College Building, Kashmere Gate, Delhi-110006' },
    'Maharashtra': { name: 'Chief Electoral Officer, Maharashtra', address: 'Mantralaya, Madam Cama Road, Hutatma Rajguru Chowk, Mumbai-400032' },
    'Karnataka': { name: 'Chief Electoral Officer, Karnataka', address: 'Kalpavriksha Bhavan, No. 40, Nrupathunga Road, Bengaluru-560001' },
    'Tamil Nadu': { name: 'Chief Electoral Officer, Tamil Nadu', address: 'Secretariat, Fort St. George, Chennai-600009' },
    'Uttar Pradesh': { name: 'Chief Electoral Officer, Uttar Pradesh', address: 'Vidhan Bhawan, Sarvodaya Nagar, Lucknow-226001' },
    'West Bengal': { name: 'Chief Electoral Officer, West Bengal', address: '21, N.S. Road, 4th Floor, Kolkata-700001' }
  };

  componentDidMount() {
    document.documentElement.setAttribute('data-theme', 'light');
    document.documentElement.setAttribute('lang', 'en');
    try {
      const p = new URLSearchParams(location.search);
      if (p.get('loggedIn') === '1' || p.get('signedIn') === '1') this.setState({ loggedIn: true, loginOpen: false });
      if (sessionStorage.getItem('eci-sir-strip') === 'dismissed') this.setState({ sirDismissed: true });
    } catch (e) {}
  }

  personas = DC.ref();

  scrollPersonas(dir) {
    const el = this.personas.current;
    if (el) el.scrollBy({ left: dir * 552, behavior: 'smooth' });
  }

  renderVals() {
    const { scale, wide, lang } = this.state;
    const opt = (on) => 'display: block; width: 100%; text-align: left; padding: 8px 10px; border: none; border-radius: 6px; background: none; font-family: inherit; font-size: 13px; line-height: 18px; cursor: pointer; font-weight: ' + (on ? '600' : '500') + '; color: ' + (on ? '#4A2BC2' : '#171717') + ';';
    const pill = (on) => 'min-width: 72px; min-height: 44px; padding: 0 16px; border-radius: 4px; font-size: 12px; line-height: 16px; font-weight: 500; cursor: pointer; border: 1px solid ' +
      (on ? '#4A2BC2' : '#D9D9D9') + '; background: ' + (on ? '#4A2BC2' : '#FFFFFF') + '; color: ' + (on ? '#FAFAFA' : '#171717') + ';';
    const accountName = 'Ananya Rao';
    const phase = this.sirPhases[this.state.sirState] || { open: false, closes: '' };
    return {
      sirState: this.state.sirState,
      sirCloseDate: phase.closes,
      sirOpenHere: phase.open,
      sirStripVisible: this.state.loggedIn && phase.open && !this.state.sirDismissed,
      sirPhaseLine: phase.open
        ? 'A phase is open in ' + this.state.sirState + '. Enumeration forms must be returned by ' + phase.closes + '.'
        : 'No phase is open in ' + this.state.sirState + ' at the moment. The dates for the next phase are yet to be confirmed.',
      onSirState: (e) => this.setState({ sirState: e.target.value }),
      dismissSir: () => {
        try { sessionStorage.setItem('eci-sir-strip', 'dismissed'); } catch (err) {}
        this.setState({ sirDismissed: true });
      },
      loggedIn: this.state.loggedIn,
      loggedOut: !this.state.loggedIn,
      loginOpen: this.state.loginOpen && !this.state.loggedIn,
      openLogin: () => this.setState({ loginOpen: true }),
      closeLogin: () => this.setState({ loginOpen: false }),
      submitLogin: (e) => { e.preventDefault(); this.setState({ loggedIn: true, loginOpen: false }); },
      userName: accountName,
      userInitials: accountName.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase(),
      showA11yBar: this.props.showAccessibilityBar ?? true,
      showAppBanner: this.props.showAppBanner ?? true,
      personasRef: this.personas,
      scrollPersonasLeft: () => this.scrollPersonas(-1),
      scrollPersonasRight: () => this.scrollPersonas(1),
      textZoom: scale,
      rootTracking: wide ? '0.06em' : 'normal',
      trackingNormal: !wide,
      trackingWide: wide,
      isEnglish: lang === 'en',
      isHindi: lang === 'hi',
      langLabel: lang === 'en' ? 'English' : 'हिन्दी',
      langOpen: !!this.state.langOpen,
      toggleLangMenu: () => this.setState(s => ({ langOpen: !s.langOpen })),
      enOptStyle: opt(lang === 'en'),
      hiOptStyle: opt(lang === 'hi'),
      toggleTracking: () => this.setState(s => ({ wide: !s.wide })),
      increaseText: () => this.setState(s => ({ scale: Math.min(1.4, +(s.scale + 0.1).toFixed(2)) })),
      decreaseText: () => this.setState(s => ({ scale: Math.max(0.85, +(s.scale - 0.1).toFixed(2)) })),
      resetText: () => this.setState({ scale: 1 }),
      setTrackingNormal: () => this.setState({ wide: false }),
      setTrackingWide: () => this.setState({ wide: true }),
      setEnglish: () => this.setState({ lang: 'en', langOpen: false }),
      setHindi: () => this.setState({ lang: 'hi', langOpen: false }),
      guidesOpen: this.state.guidesOpen,
      panelOpen: this.state.panelOpen || (this.props.openFormSheet ?? false),
      closePanel: () => this.setState({ panelOpen: false }),
      chk1: !!this.state.chk1, toggle1: () => this.setState(s => ({ chk1: !s.chk1 })),
      chk2: !!this.state.chk2, toggle2: () => this.setState(s => ({ chk2: !s.chk2 })),
      chk3: !!this.state.chk3, toggle3: () => this.setState(s => ({ chk3: !s.chk3 })),
      chk4: !!this.state.chk4, toggle4: () => this.setState(s => ({ chk4: !s.chk4 })),
      onRegisterClick: (e) => {
        e.preventDefault();
        if (!this.state.loggedIn) { this.setState({ loginOpen: true }); return; }
        location.href = 'form6-prep.html?loggedIn=1';
      },
      officeStates: Object.keys(this.offices),
      officeState: this.state.officeState,
      officeName: this.offices[this.state.officeState].name,
      officeAddress: this.offices[this.state.officeState].address,
      onOfficeChange: (e) => this.setState({ officeState: e.target.value }),
      openGuides: () => this.setState({ guidesOpen: true }),
      closeGuides: () => this.setState({ guidesOpen: false }),
      onSearchSubmit: (e) => e.preventDefault()
    };
  }
}

DC.mount(Page, document.getElementById('app'), {"showAccessibilityBar": true, "showAppBanner": true, "openFormSheet": false});
