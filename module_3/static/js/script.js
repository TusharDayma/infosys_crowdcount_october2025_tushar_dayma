// --- NEW: Global variables for history chart ---
let populationHistory = [];
let populationLabels = [];
const HISTORY_LENGTH = 50; // Max data points for the history chart

async function updateData() {
  try {
    const res = await fetch('/person_data');
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    const data = await res.json();

    // --- MODIFIED: Handle new data structure ---
    if (Object.keys(data).length === 0) {
      console.log("Waiting for data...");
      return; // Wait for tracker to initialize
    }

    const personDetails = data.person_details || {};
    const globalMetrics = data.global_metrics || {};

    // --- MODIFIED: Get element references ---
    const dataEl = document.getElementById("data");
    const alertsEl = document.getElementById("alerts");
    const totalEl = document.getElementById("total");
    const timeChartCtx = document.getElementById('timeChart');
    const historyChartCtx = document.getElementById('populationHistoryChart');
    // --- NEW: Get scatter chart canvas ---
    const scatterChartCtx = document.getElementById('scatterPlotChart');

    let alertsHtml = '';

    // --- NEW: Add global population alert first ---
    if (globalMetrics.population_alert) {
      alertsHtml += `<li class="alert-active" style="font-weight: bold; background-color: #ffcccc;">
        ZONE POPULATION ALERT: ${globalMetrics.red_zone_count} people in Red Zone!
      </li>`;
    }

    // --- NEW: Add overall population alert ---
    if (globalMetrics.overall_population_alert) {
      alertsHtml += `<li class="alert-active" style="font-weight: bold; background-color: #ffccff;">
        OVERALL POPULATION ALERT: ${globalMetrics.total_count} people in frame!
      </li>`;
    }

    // --- NEW: Prepare data for scatter plot ---
    let scatterDataRed = [];
    let scatterDataGreen = [];

    // --- MODIFIED: Only update table if it exists ---
    if (dataEl) {
      let html = `
        <table>
          <tr>
            <th>Person ID</th>
            <th>Zone</th>
            <th>Red Time (s)</th>
            <th>Green Time (s)</th>
            <th>Total Time (s)</th>
            <th>Alert</th>
            <th>Action</th>
          </tr>`;
      
      // --- Loop over per-person data ---
      for (const [id, info] of Object.entries(personDetails)) {
        const zoneColor = info["Current Zone"] === "red" ? "red" : "lime";
        const alertClass = info["Alert"] === "Yes" ? "alert-active" : "";
        html += `
          <tr>
            <td>${id}</td>
            <td style="color:${zoneColor}">${info["Current Zone"]}</td>
            <td>${info["Red Zone Time (s)"]}</td>
            <td>${info["Green Time (s)"]}</td>
            <td>${info["Total Time (s)"]}</td>
            <td class="${alertClass}">${info["Alert"]}</td>
            <td><a href="/download_pdf/${id}" target="_blank">Download PDF</a></td>
          </tr>`;
        
        // Add per-person alerts
        if (info["Alert"] === "Yes") {
          alertsHtml += `<li class="alert-active">ALERT: ${id} in danger zone too long!</li>`;
        }
        
        // --- NEW: Add data to scatter plot arrays ---
        if (info.Location) {
            const dataPoint = { x: info.Location[0], y: info.Location[1] };
            if (info["Current Zone"] === "red") {
                scatterDataRed.push(dataPoint);
            } else {
                scatterDataGreen.push(dataPoint);
            }
        }
      }
      
      html += `</table>`;
      dataEl.innerHTML = html;
    } else {
      // --- NEW: Loop for scatter data if table doesn't exist ---
      for (const [id, info] of Object.entries(personDetails)) {
        if (info.Location) {
            const dataPoint = { x: info.Location[0], y: info.Location[1] };
            if (info["Current Zone"] === "red") {
                scatterDataRed.push(dataPoint);
            } else {
                scatterDataGreen.push(dataPoint);
            }
        }
      }
    }

    // --- MODIFIED: Only update alerts if it exists ---
    if (alertsEl) {
      alertsEl.innerHTML = alertsHtml;
    }

    // --- MODIFIED: Only update total if it exists ---
    if (totalEl) {
      totalEl.innerText = globalMetrics.total_count || 0;
    }

    // --- MODIFIED: Update chart to be Zone-wise Population Chart (if it exists) ---
    if (timeChartCtx) {
      const ctx = timeChartCtx.getContext('2d');
      if (window.myChart) {
        window.myChart.destroy();
      }
      window.myChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Red Zone', 'Green Zone'], // Labels are now zones
          datasets: [
            { 
              label: 'Current Population', 
              // Data is from globalMetrics
              data: [globalMetrics.red_zone_count || 0, globalMetrics.green_zone_count || 0], 
              backgroundColor: [
                'rgba(255, 99, 132, 0.7)', // Red
                'rgba(75, 192, 192, 0.7)'  // Green
              ],
              borderColor: [
                'rgba(255, 99, 132, 1)',
                'rgba(75, 192, 192, 1)'
              ], 
              borderWidth: 1 
            }
          ]
        },
        options: {
          scales: {
            // Y-axis is now count of people
            y: { 
              beginAtZero: true, 
              title: { display: true, text: 'Number of People' },
              ticks: { color: 'rgba(236, 239, 241, 0.7)' },
              grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }, 
            x: { 
              title: { display: true, text: 'Zone' },
              ticks: { color: 'rgba(236, 239, 241, 0.7)' },
              grid: { color: 'rgba(255, 255, 255, 0.1)' }
            }
          },
          responsive: true,
          plugins: {
            legend: { 
              display: true,
              labels: { color: 'rgba(236, 239, 241, 0.9)' }
            },
            tooltip: { enabled: true }
          }
        }
      });
    }

    // --- NEW: Update history data for the line chart ---
    const now = new Date().toLocaleTimeString();
    populationLabels.push(now);
    populationHistory.push(globalMetrics.total_count || 0);

    // Limit the history length
    if (populationLabels.length > HISTORY_LENGTH) {
      populationLabels.shift();
      populationHistory.shift();
    }

    // --- NEW: Update Population Over Time line chart (if it exists) ---
    if (historyChartCtx) { // Only update if the HTML element exists
      if (window.myHistoryChart) {
        // Just update data for efficiency
        window.myHistoryChart.data.labels = populationLabels;
        window.myHistoryChart.data.datasets[0].data = populationHistory;
        window.myHistoryChart.update();
      } else {
        // Create new chart
        window.myHistoryChart = new Chart(historyChartCtx, {
          type: 'line',
          data: {
            labels: populationLabels,
            datasets: [{
              label: 'Total Population Over Time',
              data: populationHistory,
              borderColor: 'rgba(54, 162, 235, 1)',
              backgroundColor: 'rgba(54, 162, 235, 0.2)',
              fill: true,
              tension: 0.1
            }]
          },
          options: {
            scales: {
              y: { 
                beginAtZero: true, 
                title: { display: true, text: 'Number of People' },
                ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
              },
              x: { 
                title: { display: true, text: 'Time' },
                ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' }
              }
            },
            responsive: true,
            plugins: {
              legend: { 
                display: true,
                labels: { color: 'rgba(236, 239, 241, 0.9)' }
              },
              tooltip: { enabled: true }
            }
          }
        });
      }
    }

    // --- NEW: Update Scatter Plot (if it exists) ---
    if (scatterChartCtx) { 
        if (window.myScatterChart) {
            window.myScatterChart.destroy();
        }
        window.myScatterChart = new Chart(scatterChartCtx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Red Zone Person',
                    data: scatterDataRed,
                    backgroundColor: 'rgba(255, 99, 132, 0.7)',
                    pointRadius: 6
                }, {
                    label: 'Green Zone Person',
                    data: scatterDataGreen,
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    pointRadius: 6
                }]
            },
            options: {
                scales: {
                    x: {
                        min: 0,
                        max: globalMetrics.frame_width || 640, // Default 640
                        title: { display: true, text: 'X Coordinate', color: 'rgba(236, 239, 241, 0.7)' },
                        ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        min: 0,
                        max: globalMetrics.frame_height || 480, // Default 480
                        reverse: true, // <-- Invert Y-axis to match video
                        title: { display: true, text: 'Y Coordinate', color: 'rgba(236, 239, 241, 0.7)' },
                        ticks: { color: 'rgba(236, 239, 241, 0.7)' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    }
                },
                responsive: true,
                maintainAspectRatio: false, // Fit to wrapper
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: 'rgba(236, 239, 241, 0.9)' }
                    },
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) { label += ': '; }
                                if (context.parsed.x !== null && context.parsed.y !== null) {
                                    label += `(${context.parsed.x}, ${context.parsed.y})`;
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
    // --- END OF NEW SECTION ---

  } catch (error) {
    console.error('Error updating data:', error);
  }
}

async function resetTracker() {
  try {
    const res = await fetch('/reset');
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    
    // --- NEW: Clear history data ---
    populationHistory = [];
    populationLabels = [];
    if (window.myHistoryChart) {
        window.myHistoryChart.destroy();
        window.myHistoryChart = null; // Clear instance
    }
    // --- NEW: Clear scatter plot ---
    if (window.myScatterChart) {
        window.myScatterChart.destroy();
        window.myScatterChart = null;
    }

    await updateData(); // Run updateData to clear old UI elements
    
    // --- MODIFIED: Using custom modal/log instead of alert ---
    console.log('Tracker and zone reset successfully!');
    // Simple feedback without blocking alert
    const resetButton = document.querySelector('button[onclick="resetTracker()"]');
    if (resetButton) {
      const originalText = resetButton.innerText;
      resetButton.innerText = 'Reset!';
      setTimeout(() => { resetButton.innerText = originalText; }, 1500);
    }
  } catch (error) {
    console.error('Error resetting tracker:', error);
  }
}

setInterval(updateData, 1000);
updateData();