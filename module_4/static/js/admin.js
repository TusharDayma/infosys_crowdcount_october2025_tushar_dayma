// Tabbed interface logic
function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("admin-tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("admin-tab-link");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}

// Chart.js logic
document.addEventListener('DOMContentLoaded', () => {
    // Run this fetch only if the chart canvas exists
    const adminChartCtx = document.getElementById('adminAlertChart');
    if (adminChartCtx) {
        fetch('/admin/data/alert_stats')
            .then(res => res.json())
            .then(data => {
                new Chart(adminChartCtx, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Total Alerts',
                            data: data.data,
                            backgroundColor: 'rgba(233, 69, 96, 0.7)', // --secondary-color
                            borderColor: 'rgba(233, 69, 96, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: { display: true, text: 'Number of Alerts' },
                                ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            },
                            x: {
                                title: { display: true, text: 'User' },
                                ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            }
                        },
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { 
                                display: false,
                                labels: { color: 'rgba(236, 239, 241, 0.9)' }
                            }
                        }
                    }
                });
            })
            .catch(err => console.error('Error fetching admin stats:', err));
    }
});