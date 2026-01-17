"""
HTML templates for the web interface
"""
from datetime import datetime


def render_dashboard(stats):
    """Render the main dashboard"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dawarich Cleaner</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        h1 {{ color: #2563eb; margin-bottom: 10px; }}
        .subtitle {{ color: #666; font-size: 0.9rem; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #2563eb; }}
        .stat-label {{ color: #666; font-size: 0.9rem; margin-top: 5px; }}
        .card {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; font-weight: 500; color: #555; }}
        input[type="date"], input[type="number"] {{
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 1rem;
        }}
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
        }}
        .btn-primary {{
            background: #2563eb;
            color: white;
        }}
        .btn-primary:hover {{ background: #1d4ed8; }}
        .btn-secondary {{
            background: #64748b;
            color: white;
            margin-left: 10px;
        }}
        .btn-secondary:hover {{ background: #475569; }}
        .flex {{ display: flex; gap: 20px; }}
        .flex-1 {{ flex: 1; }}
        .alert {{
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}
        .alert-info {{ background: #dbeafe; color: #1e40af; border-left: 4px solid #2563eb; }}
        .alert-warning {{ background: #fef3c7; color: #92400e; border-left: 4px solid #f59e0b; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧹 Dawarich Cleaner</h1>
            <p class="subtitle">Detect and clean outlier GPS points from your Dawarich instance</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{stats.get('pending', 0)}</div>
                <div class="stat-label">Pending Review</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('deleted', 0)}</div>
                <div class="stat-label">Deleted Points</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_flagged', 0)}</div>
                <div class="stat-label">Total Flagged</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('last_scan', 'Never')}</div>
                <div class="stat-label">Last Scan</div>
            </div>
        </div>

        <div class="card">
            <h2 style="margin-bottom: 20px;">🔍 Scan for Outliers</h2>
            <form action="/scan" method="POST">
                <div class="flex">
                    <div class="flex-1">
                        <div class="form-group">
                            <label for="start_date">Start Date</label>
                            <input type="date" id="start_date" name="start_date" required>
                        </div>
                    </div>
                    <div class="flex-1">
                        <div class="form-group">
                            <label for="end_date">End Date</label>
                            <input type="date" id="end_date" name="end_date" required>
                        </div>
                    </div>
                </div>
                <div class="flex">
                    <div class="flex-1">
                        <div class="form-group">
                            <label for="max_speed">Max Speed (km/h)</label>
                            <input type="number" id="max_speed" name="max_speed" value="200" min="50" max="500">
                        </div>
                    </div>
                    <div class="flex-1">
                        <div class="form-group">
                            <label for="jump_radius">Jump Back Radius (km)</label>
                            <input type="number" id="jump_radius" name="jump_radius" value="5" min="1" max="50">
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">Start Scan</button>
                <a href="/review" class="btn btn-secondary">Review Flagged Points</a>
            </form>
        </div>

        <div class="alert alert-info">
            <strong>Detection Methods:</strong><br>
            • <strong>Jump-backs:</strong> Points that return to recent stay locations during movement<br>
            • <strong>Unrealistic speeds:</strong> Points requiring impossible travel speeds<br>
            • <strong>Oscillating:</strong> Points that create back-and-forth patterns
        </div>
    </div>
</body>
</html>
"""


def render_review(flagged_points, stats):
    """Render the review page with flagged points"""
    
    points_html = ""
    for point in flagged_points:
        detection_emoji = {
            'jump_back': '↩️',
            'unrealistic_speed': '⚡',
            'oscillating': '🔄'
        }.get(point['detection_reason'], '⚠️')
        
        timestamp_str = datetime.fromtimestamp(point['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        points_html += f"""
        <tr>
            <td><input type="checkbox" name="point_ids" value="{point['id']}" class="point-checkbox"></td>
            <td>{detection_emoji} {point['detection_reason'].replace('_', ' ').title()}</td>
            <td>{timestamp_str}</td>
            <td>{point['latitude']:.6f}, {point['longitude']:.6f}</td>
            <td>{point['confidence_score']:.2f}</td>
            <td>
                <a href="https://www.google.com/maps?q={point['latitude']},{point['longitude']}" 
                   target="_blank" class="btn-link">Map</a>
            </td>
        </tr>
        """
    
    if not points_html:
        points_html = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: #999;">No pending points to review</td></tr>'
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review Flagged Points - Dawarich Cleaner</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{ color: #2563eb; }}
        .card {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: #475569;
        }}
        tr:hover {{ background: #f8fafc; }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
            text-decoration: none;
            display: inline-block;
        }}
        .btn-primary {{ background: #2563eb; color: white; }}
        .btn-primary:hover {{ background: #1d4ed8; }}
        .btn-danger {{ background: #dc2626; color: white; margin-right: 10px; }}
        .btn-danger:hover {{ background: #b91c1c; }}
        .btn-secondary {{ background: #64748b; color: white; }}
        .btn-secondary:hover {{ background: #475569; }}
        .btn-link {{ color: #2563eb; text-decoration: none; }}
        .btn-link:hover {{ text-decoration: underline; }}
        .actions {{
            padding: 20px 0;
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .select-all {{ margin-right: auto; }}
        input[type="checkbox"] {{
            width: 18px;
            height: 18px;
            cursor: pointer;
        }}
    </style>
    <script>
        function selectAll(checked) {{
            document.querySelectorAll('.point-checkbox').forEach(cb => cb.checked = checked);
        }}
        
        function handleAction(action) {{
            const selected = Array.from(document.querySelectorAll('.point-checkbox:checked'))
                .map(cb => cb.value);
            
            if (selected.length === 0) {{
                alert('Please select at least one point');
                return;
            }}
            
            if (action === 'delete' && !confirm(`Delete ${{selected.length}} points from Dawarich?`)) {{
                return;
            }}
            
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/action/' + action;
            
            selected.forEach(id => {{
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'point_ids';
                input.value = id;
                form.appendChild(input);
            }});
            
            document.body.appendChild(form);
            form.submit();
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Review Flagged Points</h1>
            <a href="/" class="btn btn-secondary">← Back to Dashboard</a>
        </div>

        <div class="card">
            <div class="actions">
                <label class="select-all">
                    <input type="checkbox" onchange="selectAll(this.checked)">
                    Select All ({stats.get('pending', 0)} points)
                </label>
                <button onclick="handleAction('delete')" class="btn btn-danger">Delete Selected</button>
                <button onclick="handleAction('ignore')" class="btn btn-secondary">Ignore Selected</button>
            </div>

            <table>
                <thead>
                    <tr>
                        <th style="width: 50px;"></th>
                        <th>Detection Type</th>
                        <th>Timestamp</th>
                        <th>Location</th>
                        <th>Confidence</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {points_html}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""


def render_result(success, message, redirect_url="/"):
    """Render a result page"""
    status_emoji = "✅" if success else "❌"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{"Success" if success else "Error"} - Dawarich Cleaner</title>
    <meta http-equiv="refresh" content="3;url={redirect_url}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background: #f5f5f5;
        }}
        .card {{
            background: white;
            padding: 60px;
            border-radius: 10px;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 500px;
        }}
        .emoji {{ font-size: 4rem; margin-bottom: 20px; }}
        h1 {{ color: {"#10b981" if success else "#dc2626"}; margin-bottom: 15px; }}
        p {{ color: #666; margin-bottom: 30px; }}
        .redirect {{ color: #999; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="emoji">{status_emoji}</div>
        <h1>{"Success!" if success else "Error"}</h1>
        <p>{message}</p>
        <p class="redirect">Redirecting in 3 seconds...</p>
    </div>
</body>
</html>
"""
