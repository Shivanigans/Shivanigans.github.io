class Page extends DCLogic {
  state = { urlLoggedIn: false };

  componentDidMount() {
    try {
      const q = new URLSearchParams(location.search);
      if (q.get('loggedIn') === '1' || q.get('signedIn') === '1') this.setState({ urlLoggedIn: true });
    } catch (e) {}
  }

  renderVals() {
    const loggedIn = (this.props.loggedIn ?? false) || this.state.urlLoggedIn;
    const name = this.props.userName ?? 'Ananya Rao';
    return {
      homeHref: loggedIn ? 'index.html?loggedIn=1' : 'index.html',
      isLoggedIn: loggedIn,
      isLoggedOut: !loggedIn,
      userName: name,
      userInitials: name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
    };
  }
}

DC.mount(Page, document.getElementById('app'), {"loggedIn": false, "userName": "Ananya Rao"});
