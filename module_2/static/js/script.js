async function updateData() {
  try {
    const res = await fetch('/person_data');
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    const data = await res.json();

    // Update table
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
    let alertsHtml = '';
    let labels = [], redData = [], greenData = [];

    for (const [id, info] of Object.entries(data)) {
      const zoneColor = info["Current Zone"] === "red" ? "red" : "lime";
      const alertClass = info["Alert"] === "Yes" ? "alert-active" : "";
      html += `
        <tr>
          <td>${id}</td>
          <td style="color:${zoneColor}">${info["Current Zone"]}</td>
          <td>${info["Red Zone Time (s)"]}</td>
          <td>${info["Green Zone Time (s)"]}</td>
          <td>${info["Total Time (s)"]}</td>
          <td class="${alertClass}">${info["Alert"]}</td>
          <td><a href="/download_pdf/${id}" target="_blank">Download PDF</a></td>
        </tr>`;
      
      if (info["Alert"] === "Yes") {
        alertsHtml += `<li class="alert-active">ALERT: ${id} in danger zone too long!</li>`;
      }

      labels.push(id);
      redData.push(info["Red Zone Time (s)"]);
      greenData.push(info["Green Zone Time (s)"]);
    }
    html += `</table>`;
    document.getElementById("data").innerHTML = html;
    document.getElementById("alerts").innerHTML = alertsHtml;

    // Update total count
    document.getElementById("total").innerText = Object.keys(data).length;

    // Update chart
    const ctx = document.getElementById('timeChart').getContext('2d');
    if (window.myChart) {
      window.myChart.destroy();
    }
    window.myChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Red Zone', data: redData, backgroundColor: 'rgba(255, 99, 132, 0.7)', borderColor: 'rgba(255, 99, 132, 1)', borderWidth: 1 },
          { label: 'Green Zone', data: greenData, backgroundColor: 'rgba(75, 192, 192, 0.7)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 }
        ]
      },
      options: {
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Time (s)' } },
          x: { title: { display: true, text: 'Person ID' } }
        },
        responsive: true,
        plugins: {
          legend: { display: true },
          tooltip: { enabled: true }
        }
      }
    });
  } catch (error) {
    console.error('Error updating data:', error);
  }
}

async function resetTracker() {
  try {
    const res = await fetch('/reset');
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    await updateData();
    alert('Tracker and zone reset successfully!');
  } catch (error) {
    console.error('Error resetting tracker:', error);
    alert('Failed to reset tracker');
  }
}

setInterval(updateData, 1000);
updateData();