class Page extends DCLogic {
  renderVals() {
    return {
      onSubmit: (e) => {
        e.preventDefault();
        location.href = 'index.html?loggedIn=1';
      }
    };
  }
}

DC.mount(Page, document.getElementById('app'), {});
