function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('active');
    document.getElementById('main-content').classList.toggle('active');
    document.querySelector('.toggle-btn').classList.toggle('active');
}