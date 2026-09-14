class Page extends DCLogic {
  sectionList = [
    { key: 'constituency', id: 'constituency', label: 'Select state, district and constituency' },
    { key: 'personal', id: 'your-details', label: 'Personal details' },
    { key: 'relative', id: 'relative', label: 'Parent or spouse details' },
    { key: 'contact', id: 'contact', label: 'Contact details' },
    { key: 'aadhaar', id: 'aadhaar', label: 'Aadhaar details' },
    { key: 'gender', id: 'gender', label: 'Gender' },
    { key: 'dob', id: 'dob', label: 'Date of birth details' },
    { key: 'address', id: 'address', label: 'Present address details' },
    { key: 'disability', id: 'disability', label: 'Disability details' },
    { key: 'family', id: 'family', label: 'Family member details' },
    { key: 'declaration', id: 'declaration', label: 'Declaration' },
    { key: 'security', id: 'security', label: 'Captcha' }
  ];

  strictSections = ['constituency', 'your-details', 'relative'];

  acNumbers = { 'Huzur': '155', 'Bhopal Madhya': '152', 'Narela': '151', 'Govindpura': '153' };

  messages = {
    'state': 'Select your state or union territory.',
    'district': 'Select your district.',
    'ac-name': 'Select your assembly constituency.',
    'ac-number': 'Enter the constituency number, using digits only.',
    'pc-name': 'Select your parliamentary constituency.',
    'pc-number': 'Enter the constituency number, using digits only.',
    'first-name': 'Enter your first name as it appears on your Aadhaar card.',
    'rel-name': 'Enter the name of your parent or spouse.',
    'rel-type': 'Select a relationship.',
    'mobile': 'Enter a ten digit mobile number.',
    'email': 'Enter an email address in the format name@example.com.',
    'aadhaar-number': 'Enter all twelve digits of your Aadhaar number.',
    'dob-date': 'Enter your date of birth.',
    'house': 'Enter your house or flat number.',
    'street': 'Enter your street or locality.',
    'town': 'Enter your town or village.',
    'post-office': 'Enter your post office.',
    'pin': 'Enter a six digit pin code.',
    'addr-district': 'Select your district.',
    'family-name': 'Enter the name of the family member.',
    'family-relation': 'Select a relationship.',
    'family-epic': 'Enter a ten character voter ID, three letters followed by seven digits.',
    'decl-place': 'Enter the place where you are making this declaration.',
    'decl-date': 'Enter the date.',
    'captcha': 'Enter the code shown above.',
    'gender': 'Select your gender.',
    'declaration-confirm': 'Tick the declaration to continue.'
  };

  controlsIn(sectionId) {
    const root = document.getElementById(sectionId);
    if (!root) return [];
    return Array.prototype.slice.call(root.querySelectorAll('input, select, textarea'))
      .filter(el => el.willValidate && el.type !== 'file');
  }

  checkSection(sectionId) {
    const found = {};
    this.controlsIn(sectionId).forEach(el => {
      const key = el.id || el.name;
      if (!key || el.checkValidity()) return;
      found[key] = this.messages[key] || el.validationMessage;
    });
    return found;
  }

  applyErrors(sectionId, found) {
    const errors = Object.assign({}, this.state.errors);
    this.controlsIn(sectionId).forEach(el => { delete errors[el.id || el.name]; });
    Object.keys(found).forEach(k => { errors[k] = found[k]; });
    return errors;
  }

  saveOrShowErrors(sectionId, proceed) {
    const found = this.checkSection(sectionId);
    const errors = this.applyErrors(sectionId, found);
    const keys = Object.keys(found);
    const validated = this.state.validated.indexOf(sectionId) > -1 ? this.state.validated : this.state.validated.concat([sectionId]);
    this.setState({ errors: errors, validated: validated });
    if (keys.length) {
      const first = this.controlsIn(sectionId).filter(el => (el.id || el.name) === keys[0])[0];
      if (first && first.focus) setTimeout(() => first.focus(), 0);
      return;
    }
    proceed();
  }

  componentDidMount() {
    this.liveCheck = (e) => {
      const el = e.target;
      if (!el || !el.closest) return;
      const sec = el.closest('section[id]');
      if (!sec || this.state.validated.indexOf(sec.id) < 0) return;
      const found = this.checkSection(sec.id);
      this.setState({ errors: this.applyErrors(sec.id, found) });
    };
    document.addEventListener('input', this.liveCheck, true);
    document.addEventListener('change', this.liveCheck, true);
  }

  componentWillUnmount() {
    document.removeEventListener('input', this.liveCheck, true);
    document.removeEventListener('change', this.liveCheck, true);
  }


  state = {
    active: 'constituency',
    open: 'constituency',
    errors: {},
    validated: [],
    done: [],
    type: 'assembly',
    tip: null,
    noAadhaar: false,
    declared: false,
    captchaCode: '4KQ7M',
    leaveOpen: false,
    leaveHref: 'index.html?loggedIn=1',
    screen: 'form',
    refNumber: '',
    copied: false,
    disabilities: { visual: false, hearing: false, locomotor: false, other: false },
    values: {
      state: 'Madhya Pradesh', district: 'Bhopal', acName: 'Huzur', acNumber: '155',
      firstName: 'Ananya Devi', surname: 'Rao', nameRegional: 'अनन्या देवी राव',
      relativeName: 'Suresh Rao', relativeRelation: 'father',
      mobile: '98765 43210', email: 'ananya.rao@example.com',
      aadhaar: '2345 6789 0123',
      gender: 'female',
      dob: '2008-04-17',
      house: '14-B, Ashoka Apartments', street: 'Shivaji Nagar', town: 'Bhopal',
      postOffice: 'Shivaji Nagar', pin: '462016', addrDistrict: 'Bhopal',
      familyName: 'Suresh Rao', familyRelation: 'father', familyEpic: 'MPZ1234567',
      place: 'Bhopal', declDate: '2026-09-12', captcha: ''
    }
  };

  scrollTo(id) {
    setTimeout(() => {
      const el = document.getElementById(id);
      const se = document.scrollingElement || document.documentElement;
      if (el && se) se.scrollTop = el.getBoundingClientRect().top + se.scrollTop - 88;
    }, 0);
  }

  jump(id) {
    return (e) => {
      e.preventDefault();
      this.openSection(id);
    };
  }

  openSection(id) {
    this.setState({ open: id, active: id || this.state.active });
    if (id) this.scrollTo(id);
  }

  saveSection(id) {
    const ids = this.sectionList.map(s => s.id);
    const next = this.sectionList[ids.indexOf(id) + 1];
    const done = this.state.done.indexOf(id) > -1 ? this.state.done : this.state.done.concat([id]);
    this.setState({ done: done, open: next ? next.id : null, active: next ? next.id : id });
    if (next) this.scrollTo(next.id);
  }

  goToPreview() {
    const done = this.state.done.indexOf('security') > -1 ? this.state.done : this.state.done.concat(['security']);
    this.setState({ done: done, open: null, screen: 'preview' });
    setTimeout(() => {
      const se = document.scrollingElement || document.documentElement;
      if (se) se.scrollTop = 0;
    }, 0);
  }

  editSection(id) {
    return () => {
      this.setState({ screen: 'form', open: id, active: id });
      this.scrollTo(id);
    };
  }

  previewRows() {
    const v = this.state.values;
    const dis = this.state.disabilities;
    const genderLabels = { male: 'Male', female: 'Female', third: 'Third gender' };
    const disList = [];
    if (dis.visual) disList.push('Visual impairment');
    if (dis.hearing) disList.push('Speech or hearing disability');
    if (dis.locomotor) disList.push('Locomotor disability');
    if (dis.other) disList.push('Another disability');
    const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
    const assembly = this.state.type === 'assembly';
    return [
      { letter: 'A', id: 'constituency', heading: 'Constituency details', rows: [
        { label: 'State or union territory', value: v.state },
        { label: 'District', value: v.district },
        { label: assembly ? 'Assembly constituency name' : 'Parliamentary constituency name', value: v.acName },
        { label: assembly ? 'Assembly constituency number' : 'Parliamentary constituency number', value: v.acNumber }
      ] },
      { letter: 'B', id: 'your-details', heading: 'Applicant details', rows: [
        { label: 'First name and middle name', value: v.firstName },
        { label: 'Surname', value: v.surname },
        { label: 'Name in regional language', value: v.nameRegional },
        { label: 'Passport size photograph', value: this.state.done.indexOf('your-details') > -1 ? 'Attached' : '' }
      ] },
      { letter: 'C', id: 'relative', heading: 'Details of parent or spouse', rows: [
        { label: 'Name', value: v.relativeName },
        { label: 'Relationship to the applicant', value: cap(v.relativeRelation) }
      ] },
      { letter: 'D', id: 'contact', heading: 'Contact details', rows: [
        { label: 'Mobile number', value: v.mobile },
        { label: 'Email address', value: v.email }
      ] },
      { letter: 'E', id: 'aadhaar', heading: 'Aadhaar details', rows: [
        { label: 'Aadhaar number', value: this.state.noAadhaar ? '' : v.aadhaar },
        { label: 'No Aadhaar number held', value: this.state.noAadhaar ? 'Declared' : '' }
      ] },
      { letter: 'F', id: 'gender', heading: 'Gender', rows: [
        { label: 'Gender', value: genderLabels[v.gender] || '' }
      ] },
      { letter: 'G', id: 'dob', heading: 'Date of birth details', rows: [
        { label: 'Date of birth', value: v.dob },
        { label: 'Proof of date of birth', value: this.state.done.indexOf('dob') > -1 ? 'Attached' : '' }
      ] },
      { letter: 'H', id: 'address', heading: 'Details of present ordinary residence', rows: [
        { label: 'House or flat number', value: v.house },
        { label: 'Street or locality', value: v.street },
        { label: 'Town or village', value: v.town },
        { label: 'Post office', value: v.postOffice },
        { label: 'Pin code', value: v.pin },
        { label: 'District', value: v.addrDistrict },
        { label: 'Proof of present address', value: this.state.done.indexOf('address') > -1 ? 'Attached' : '' }
      ] },
      { letter: 'I', id: 'disability', heading: 'Disability details', rows: [
        { label: 'Disability', value: disList.join(', ') },
        { label: 'Disability certificate', value: '' }
      ] },
      { letter: 'J', id: 'family', heading: 'Details of a family member already in the roll', rows: [
        { label: 'Name', value: v.familyName },
        { label: 'Relationship to the applicant', value: cap(v.familyRelation) },
        { label: 'Voter ID number', value: v.familyEpic }
      ] },
      { letter: 'K', id: 'declaration', heading: 'Declaration', rows: [
        { label: 'Place', value: v.place },
        { label: 'Date', value: v.declDate },
        { label: 'Declaration confirmed', value: this.state.declared ? 'Yes' : '' }
      ] },
      { letter: 'L', id: 'security', heading: 'Verification', rows: [
        { label: 'Code entered', value: v.captcha }
      ] }
    ];
  }

  confirmLeave(href) {
    return (e) => {
      e.preventDefault();
      this.setState({ leaveOpen: true, leaveHref: href });
    };
  }

  setVal(k) {
    return (e) => {
      const values = Object.assign({}, this.state.values);
      values[k] = e.target.value;
      this.setState({ values: values });
    };
  }

  setValTo(k, val) {
    const values = Object.assign({}, this.state.values);
    values[k] = val;
    this.setState({ values: values });
  }

  renderVals() {
    const name = this.props.userName ?? 'Ananya Rao';
    const done = this.state.done;
    const total = this.sectionList.length;
    const filled = done.length;
    const exact = (filled / total) * 100;
    let rounded = Math.round(exact / 10) * 10;
    if (filled === 0) rounded = 0;
    else if (rounded === 0) rounded = 10;
    if (rounded >= 100 && filled < total) rounded = 90;
    if (filled === total) rounded = 100;

    const rowBase = 'display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 36px; padding: 7px 12px 7px 13px; border-top: 1px solid #EDEDED; text-decoration: none; background: #FFFFFF;';
    const sections = this.sectionList.map(s => {
      const active = this.state.active === s.id;
      return {
        label: s.label,
        href: '#' + s.id,
        active: active,
        inactive: !active,
        done: done.indexOf(s.id) > -1,
        onClick: this.jump(s.id),
        rowStyle: active
          ? 'display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 36px; padding: 7px 12px 7px 10px; border-top: 1px solid #EDEDED; border-left: 3px solid #4A2BC2; text-decoration: none; background: #F3F0FF;'
          : rowBase,
        labelStyle: active
          ? 'font-size: 14px; line-height: 20px; font-weight: 600; color: #4A2BC2; text-wrap: pretty;'
          : 'font-size: 14px; line-height: 20px; color: #404040; text-wrap: pretty;'
      };
    });

    const heads = {};
    this.sectionList.forEach((s, i) => {
      const open = this.state.open === s.id;
      const isDone = done.indexOf(s.id) > -1;
      const prev = this.sectionList[i - 1];
      heads[s.key] = {
        label: s.label,
        open: open,
        done: isDone,
        onClick: () => this.openSection(open ? null : s.id),
        onSave: (() => {
          const last = i === this.sectionList.length - 1;
          const proceed = last ? () => this.goToPreview() : () => this.saveSection(s.id);
          return this.strictSections.indexOf(s.id) > -1 ? () => this.saveOrShowErrors(s.id, proceed) : proceed;
        })(),
        onPrevious: () => this.openSection(prev ? prev.id : s.id),
        cardStyle: 'background: #FFFFFF; border: 1px solid ' + (open ? '#DDD5F7' : '#E5E5E5') + '; border-radius: 12px; overflow: hidden;',
        rowStyle: 'display: flex; align-items: center; gap: 12px; width: 100%; box-sizing: border-box; min-height: 56px; padding: 14px 24px; border: none; border-bottom: 1px solid ' + (open ? '#DDD5F7' : 'transparent') + '; background: ' + (open ? '#F3F0FF' : '#FFFFFF') + '; font-family: inherit; text-align: left; cursor: pointer;',
        titleStyle: 'flex: 1 1 auto; min-width: 0; font-size: ' + (open ? '17px' : '16px') + '; line-height: 24px; font-weight: 600; color: ' + (open || isDone ? '#171717' : '#525252') + '; text-wrap: pretty;',
        chevStyle: 'flex: 0 0 auto; transition: transform 160ms ease; transform: rotate(' + (open ? '180deg' : '0deg') + ');'
      };
    });

    const v = this.state.values;
    const tip = this.state.tip;
    const dis = this.state.disabilities;
    const toggleDis = (k) => () => {
      const next = Object.assign({}, dis);
      next[k] = !next[k];
      this.setState({ disabilities: next });
    };

    const errState = this.state.errors;
    const errs = {};
    ['state', 'district', 'ac-name', 'ac-number', 'pc-name', 'pc-number', 'first-name', 'surname', 'name-regional', 'photo', 'rel-name', 'rel-type', 'mobile', 'email', 'aadhaar-number', 'dob-date', 'dob-proof', 'house', 'street', 'town', 'post-office', 'pin', 'addr-district', 'addr-proof', 'disability-cert', 'family-name', 'family-relation', 'family-epic', 'decl-place', 'decl-date', 'captcha', 'gender', 'declaration-confirm'].forEach(k => {
      const camel = k.replace(/-([a-z])/g, (m, c) => c.toUpperCase());
      errs[camel] = { show: !!errState[k], msg: errState[k] || '' };
    });

    return {
      errs: errs,
      userName: name,
      userInitials: name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase(),
      sections,
      heads,
      v: v,
      pctExact: Math.round(exact),
      barWidth: exact.toFixed(1) + '%',
      pctLabel: rounded + '%',

      isAssembly: this.state.type === 'assembly',
      isParliamentary: this.state.type === 'parliamentary',
      chooseAssembly: () => this.setState({ type: 'assembly' }),
      chooseParliamentary: () => this.setState({ type: 'parliamentary' }),

      tips: { ac: tip === 'ac', first: tip === 'first', name: tip === 'name', epic: tip === 'epic' },
      tipAc: () => this.setState({ tip: 'ac' }),
      tipFirst: () => this.setState({ tip: 'first' }),
      tipName: () => this.setState({ tip: 'name' }),
      tipEpic: () => this.setState({ tip: 'epic' }),
      hideTip: () => this.setState({ tip: null }),

      on: {
        state: this.setVal('state'),
        district: this.setVal('district'),
        acNumber: this.setVal('acNumber'),
        firstName: this.setVal('firstName'),
        surname: this.setVal('surname'),
        nameRegional: this.setVal('nameRegional'),
        relativeName: this.setVal('relativeName'),
        relativeRelation: this.setVal('relativeRelation'),
        mobile: this.setVal('mobile'),
        email: this.setVal('email'),
        dob: this.setVal('dob'),
        house: this.setVal('house'),
        street: this.setVal('street'),
        town: this.setVal('town'),
        postOffice: this.setVal('postOffice'),
        addrDistrict: this.setVal('addrDistrict'),
        familyName: this.setVal('familyName'),
        familyRelation: this.setVal('familyRelation'),
        familyEpic: this.setVal('familyEpic'),
        place: this.setVal('place'),
        declDate: this.setVal('declDate'),
        captcha: this.setVal('captcha'),
        genderMale: () => this.setValTo('gender', 'male'),
        genderFemale: () => this.setValTo('gender', 'female'),
        genderThird: () => this.setValTo('gender', 'third'),
        dVisual: toggleDis('visual'),
        dHearing: toggleDis('hearing'),
        dLocomotor: toggleDis('locomotor'),
        dOther: toggleDis('other')
      },

      onAcName: (e) => {
        const values = Object.assign({}, this.state.values);
        values.acName = e.target.value;
        values.acNumber = this.acNumbers[e.target.value] || '';
        this.setState({ values: values });
      },
      onAadhaar: (e) => {
        const digits = e.target.value.replace(/[^0-9]/g, '').slice(0, 12);
        const groups = [];
        for (let i = 0; i < digits.length; i += 4) groups.push(digits.slice(i, i + 4));
        this.setValTo('aadhaar', groups.join(' '));
      },
      onPin: (e) => this.setValTo('pin', e.target.value.replace(/[^0-9]/g, '').slice(0, 6)),

      hasAadhaar: !this.state.noAadhaar,
      noAadhaar: this.state.noAadhaar,
      toggleNoAadhaar: () => this.setState({ noAadhaar: !this.state.noAadhaar }),

      g: { male: v.gender === 'male', female: v.gender === 'female', third: v.gender === 'third' },
      d: dis,

      declared: this.state.declared,
      toggleDeclared: () => this.setState({ declared: !this.state.declared }),

      leaveOpen: this.state.leaveOpen,
      leaveHref: this.state.leaveHref,
      openLeave: () => this.setState({ leaveOpen: true, leaveHref: 'index.html?loggedIn=1' }),
      closeLeave: () => this.setState({ leaveOpen: false }),
      leaveTo: {
        home: this.confirmLeave('index.html?loggedIn=1'),
        register: this.confirmLeave('index.html?loggedIn=1'),
        prep: this.confirmLeave('form6-prep.html')
      },

      screenTrack: this.state.screen === 'track',
      goToTrack: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        this.setState({ screen: 'track' });
        setTimeout(() => { const se = document.scrollingElement || document.documentElement; if (se) se.scrollTop = 0; }, 0);
      },
      screenForm: this.state.screen === 'form',
      screenPreview: this.state.screen === 'preview',
      screenDone: this.state.screen === 'done',
      eroLine: (v.acName ? v.acName + ' assembly constituency, ' : '') + (v.district || '') + (v.state ? ', ' + v.state : ''),
      previewSections: this.previewRows().map(sec => ({
        title: sec.letter + '. ' + sec.heading,
        onEdit: this.editSection(sec.id),
        rows: sec.rows.map(r => ({
          label: r.label,
          value: r.value || '',
          valueStyle: (r.value || '') === ''
            ? 'margin: 0; font-size: 14px; line-height: 20px; min-height: 20px; border-bottom: 1px dashed #D4D4D4;'
            : 'margin: 0; font-size: 14px; line-height: 20px; font-weight: 500; color: #171717; text-wrap: pretty;'
        }))
      })),
      backToForm: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        this.setState({ screen: 'form', open: 'security', active: 'security' });
        this.scrollTo('security');
      },
      submitDisabled: !this.state.declared,
      submitStyle: this.state.declared
        ? 'display: inline-flex; align-items: center; justify-content: center; margin-left: auto; min-height: 48px; padding: 0 28px; border: none; border-radius: 8px; background: #4A2BC2; color: #FAFAFA; font-family: inherit; font-size: 15px; font-weight: 600; cursor: pointer;'
        : 'display: inline-flex; align-items: center; justify-content: center; margin-left: auto; min-height: 48px; padding: 0 28px; border: none; border-radius: 8px; background: #E5E5E5; color: #8A8A8A; font-family: inherit; font-size: 15px; font-weight: 600; cursor: not-allowed;',
      submitApplication: () => {
        let digits = '';
        for (let i = 0; i < 6; i++) digits += Math.floor(Math.random() * 10);
        this.setState({ screen: 'done', refNumber: 'MP/BHO/2026/' + digits, copied: false });
        setTimeout(() => {
          const se = document.scrollingElement || document.documentElement;
          if (se) se.scrollTop = 0;
        }, 0);
      },
      refNumber: this.state.refNumber,
      trackHref: 'index.html?ref=' + encodeURIComponent(this.state.refNumber),
      copyLabel: this.state.copied ? 'Copied' : 'Copy code',
      copyRef: () => {
        if (navigator.clipboard) navigator.clipboard.writeText(this.state.refNumber);
        this.setState({ copied: true });
        setTimeout(() => this.setState({ copied: false }), 2000);
      },

      captchaCode: this.state.captchaCode,
      newCaptcha: () => {
        const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        let code = '';
        for (let i = 0; i < 5; i++) code += chars[Math.floor(Math.random() * chars.length)];
        this.setState({ captchaCode: code });
      }
    };
  }
}

DC.mount(Page, document.getElementById('app'), {"userName": "Ananya Rao"});
