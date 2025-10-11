(function applyStoredTheme() {
    try {
        const storedTheme = localStorage.getItem('qn-theme');
        if (storedTheme) {
            document.documentElement.setAttribute('data-theme', storedTheme);
        }
    } catch (error) {
        console.warn('Unable to read stored theme preference.', error);
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    const profileToggle = document.querySelector('[data-profile-toggle]');
    const profileDropdown = document.querySelector('[data-profile-dropdown]');

    if (profileToggle && profileDropdown) {
        const closeDropdown = () => {
            if (profileDropdown.hasAttribute('hidden')) {
                return;
            }
            profileDropdown.hidden = true;
            profileDropdown.classList.remove('is-open');
            profileToggle.setAttribute('aria-expanded', 'false');
        };

        profileToggle.addEventListener('click', event => {
            event.preventDefault();
            const isExpanded = profileToggle.getAttribute('aria-expanded') === 'true';
            if (isExpanded) {
                closeDropdown();
            } else {
                profileDropdown.hidden = false;
                profileDropdown.classList.add('is-open');
                profileToggle.setAttribute('aria-expanded', 'true');
                profileDropdown.focus();
            }
        });

        document.addEventListener('click', event => {
            if (!profileDropdown.contains(event.target) && !profileToggle.contains(event.target)) {
                closeDropdown();
            }
        });

        profileDropdown.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                closeDropdown();
                profileToggle.focus();
            }
        });
    }

    document.querySelectorAll('[data-confirm-delete]').forEach(form => {
        form.addEventListener('submit', event => {
            const confirmed = window.confirm('Are you sure you want to delete your account? This action cannot be undone.');
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    const themeToggle = document.querySelector('[data-theme-toggle]');
    if (themeToggle) {
        const applyTheme = isDark => {
            const theme = isDark ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', theme);
            try {
                localStorage.setItem('qn-theme', theme);
            } catch (error) {
                console.warn('Unable to persist theme preference.', error);
            }
        };

        try {
            const storedTheme = localStorage.getItem('qn-theme');
            if (storedTheme) {
                themeToggle.checked = storedTheme === 'dark';
            }
        } catch (error) {
            console.warn('Unable to read stored theme preference.', error);
        }

        applyTheme(themeToggle.checked);
        themeToggle.addEventListener('change', () => applyTheme(themeToggle.checked));
    }

    document.querySelectorAll('[data-pref-toggle]').forEach(toggle => {
        const storageKey = toggle.dataset.prefToggle;
        if (!storageKey) {
            return;
        }

        try {
            const storedValue = localStorage.getItem(storageKey);
            if (storedValue !== null) {
                toggle.checked = storedValue === 'true';
            }
        } catch (error) {
            console.warn('Unable to read preference', storageKey, error);
        }

        toggle.addEventListener('change', () => {
            try {
                localStorage.setItem(storageKey, toggle.checked);
            } catch (error) {
                console.warn('Unable to persist preference', storageKey, error);
            }
        });
    });
});
