// School Management System (SchoolSM) JavaScript Helpers

document.addEventListener('DOMContentLoaded', function() {
    // Initialize collapsible sidebar menu sections
    initSidebarSections();

    // Sidebar auto-scroll & position management
    const sidebar = document.querySelector('.app-sidebar');
    if (sidebar) {
        // Scroll active menu item clearly into view
        scrollActiveSidebarMenu(false);

        // Handle click on sidebar links to record scroll target and smoothly show item
        const menuLinks = sidebar.querySelectorAll('.menu-link');
        menuLinks.forEach(function(link) {
            link.addEventListener('click', function() {
                const brand = sidebar.querySelector('.sidebar-brand');
                const brandHeight = brand ? brand.offsetHeight : 0;
                const sidebarRect = sidebar.getBoundingClientRect();
                const linkRect = this.getBoundingClientRect();
                const availableHeight = sidebar.clientHeight - brandHeight;
                const targetScrollTop = (sidebar.scrollTop + (linkRect.top - sidebarRect.top)) - brandHeight - (availableHeight / 2) + (this.clientHeight / 2);
                
                sessionStorage.setItem('sidebar_scroll_pos', Math.max(0, targetScrollTop));

                // Auto-close sidebar on mobile after clicking
                if (window.innerWidth < 992 && sidebar.classList.contains('show')) {
                    sidebar.classList.remove('show');
                }
            });
        });

        // Save manual scroll position
        let scrollTimeout;
        sidebar.addEventListener('scroll', function() {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(function() {
                sessionStorage.setItem('sidebar_scroll_pos', sidebar.scrollTop);
            }, 100);
        }, { passive: true });
    }

    // Re-verify scroll on window load (after fonts and layout settle)
    window.addEventListener('load', function() {
        scrollActiveSidebarMenu(false);
    });

    // Restore desktop collapsed state
    if (window.innerWidth >= 992 && localStorage.getItem('sidebar_collapsed') === 'true') {
        document.body.classList.add('sidebar-collapsed');
        document.documentElement.classList.add('sidebar-collapsed');
    }

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert.alert-dismissible');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Toggle collapsible sidebar section (Accordion mode: only one section open at a time)
function toggleMenuSection(sectionId) {
    const targetSection = document.getElementById(sectionId);
    if (!targetSection) return;

    const targetBtn = document.getElementById('btn-' + sectionId) || targetSection.previousElementSibling;
    const isCurrentlyCollapsed = targetSection.classList.contains('is-collapsed');

    // 1. Collapse ALL other sections
    const allSections = document.querySelectorAll('.menu-sub-list');
    allSections.forEach(function(sec) {
        sec.classList.add('is-collapsed');
        const btn = document.getElementById('btn-' + sec.id) || sec.previousElementSibling;
        if (btn) {
            btn.classList.add('is-collapsed');
            btn.setAttribute('aria-expanded', 'false');
        }
    });

    // 2. If target was collapsed, expand it only
    if (isCurrentlyCollapsed) {
        targetSection.classList.remove('is-collapsed');
        if (targetBtn) {
            targetBtn.classList.remove('is-collapsed');
            targetBtn.setAttribute('aria-expanded', 'true');
        }
        try {
            localStorage.setItem('sidebar_active_accordion', sectionId);
        } catch(e) {}
    } else {
        // Target was already open, user clicked to collapse it
        try {
            localStorage.setItem('sidebar_active_accordion', '');
        } catch(e) {}
    }
}

// Initialize and restore state of all collapsible sidebar sections (Single Open Section)
function initSidebarSections() {
    const allSections = document.querySelectorAll('.menu-sub-list');
    if (!allSections.length) return;

    let activeSectionId = null;

    // Priority 1: Section containing the current active link
    allSections.forEach(function(sec) {
        if (sec.querySelector('.menu-link.active')) {
            activeSectionId = sec.id;
        }
    });

    // Priority 2: Last user opened section from localStorage or default to sec-dashboard
    if (!activeSectionId) {
        try {
            const saved = localStorage.getItem('sidebar_active_accordion');
            if (saved && document.getElementById(saved)) {
                activeSectionId = saved;
            } else {
                activeSectionId = 'sec-dashboard';
            }
        } catch(e) {
            activeSectionId = 'sec-dashboard';
        }
    }

    // Apply Accordion state: ONLY activeSectionId is open, all others collapsed
    allSections.forEach(function(sec) {
        const btn = document.getElementById('btn-' + sec.id) || sec.previousElementSibling;
        if (sec.id === activeSectionId) {
            sec.classList.remove('is-collapsed');
            if (btn) {
                btn.classList.remove('is-collapsed');
                if (sec.querySelector('.menu-link.active')) {
                    btn.classList.add('has-active');
                }
                btn.setAttribute('aria-expanded', 'true');
            }
        } else {
            sec.classList.add('is-collapsed');
            if (btn) {
                btn.classList.add('is-collapsed');
                btn.classList.remove('has-active');
                btn.setAttribute('aria-expanded', 'false');
            }
        }
    });
}

// Global function to toggle sidebar across all screen sizes
function toggleAppSidebar() {
    const sidebar = document.querySelector('.app-sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar) return;

    if (window.innerWidth < 992) {
        // Mobile behavior (Offcanvas slide in/out)
        const isShown = sidebar.classList.toggle('show');
        if (backdrop) {
            backdrop.classList.toggle('show', isShown);
        }
        if (isShown && typeof scrollActiveSidebarMenu === 'function') {
            scrollActiveSidebarMenu(false);
        }
    } else {
        // Desktop behavior (Collapse/Expand main area)
        const isCurrentlyCollapsed = document.body.classList.contains('sidebar-collapsed');
        if (isCurrentlyCollapsed) {
            // UNHIDE / EXPAND
            document.body.classList.remove('sidebar-collapsed');
            document.documentElement.classList.remove('sidebar-collapsed');
            localStorage.setItem('sidebar_collapsed', 'false');
        } else {
            // HIDE / COLLAPSE
            document.body.classList.add('sidebar-collapsed');
            document.documentElement.classList.add('sidebar-collapsed');
            localStorage.setItem('sidebar_collapsed', 'true');
        }
    }
}

// Global function to close mobile sidebar
function closeMobileSidebar() {
    const sidebar = document.querySelector('.app-sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (sidebar) sidebar.classList.remove('show');
    if (backdrop) backdrop.classList.remove('show');
}

// Helper function to calculate and center active sidebar menu item
function scrollActiveSidebarMenu(smooth = false) {
    const sidebar = document.querySelector('.app-sidebar');
    if (!sidebar) return;

    const activeLink = sidebar.querySelector('.menu-link.active');
    if (activeLink) {
        const brand = sidebar.querySelector('.sidebar-brand');
        const brandHeight = brand ? brand.offsetHeight : 0;
        const sidebarRect = sidebar.getBoundingClientRect();
        const activeRect = activeLink.getBoundingClientRect();
        const availableHeight = sidebar.clientHeight - brandHeight;
        const targetScrollTop = (sidebar.scrollTop + (activeRect.top - sidebarRect.top)) - brandHeight - (availableHeight / 2) + (activeLink.clientHeight / 2);
        
        if (smooth) {
            sidebar.scrollTo({
                top: Math.max(0, targetScrollTop),
                behavior: 'smooth'
            });
        } else {
            sidebar.scrollTop = Math.max(0, targetScrollTop);
        }
    } else {
        const savedScroll = sessionStorage.getItem('sidebar_scroll_pos');
        if (savedScroll !== null) {
            sidebar.scrollTop = parseInt(savedScroll, 10);
        }
    }
}

// Quick helper to select all checkboxes (e.g. for promotion or bulk actions)
function toggleSelectAll(masterCheckbox, targetCheckboxClass) {
    const checkboxes = document.querySelectorAll('.' + targetCheckboxClass);
    checkboxes.forEach(cb => {
        cb.checked = masterCheckbox.checked;
    });
}

// Mark all present in Attendance sheet
function markAllPresent() {
    const presentRadios = document.querySelectorAll('input[type="radio"][value="PRESENT"]');
    presentRadios.forEach(radio => {
        radio.checked = true;
    });
}
