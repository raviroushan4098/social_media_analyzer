import json
import httpx
from urllib.parse import quote
from typing import Dict, Any, List
import jmespath
import pandas as pd
from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from django.conf import settings
from .forms import UploadCSVForm
import io

INSTAGRAM_DOCUMENT_ID = "8845758582119845"

def scrape_post(shortcode: str) -> Dict[str, Any]:
    print(f"Scraping Instagram post: {shortcode}")
    variables = quote(json.dumps({
        'shortcode': shortcode,
        'fetch_tagged_user_count': None,
        'hoisted_comment_id': None,
        'hoisted_reply_id': None
    }, separators=(',', ':')))
    body = f"variables={variables}&doc_id={INSTAGRAM_DOCUMENT_ID}"
    url = "https://www.instagram.com/graphql/query"
    try:
        result = httpx.post(
            url=url,
            headers={"content-type": "application/x-www-form-urlencoded"},
            data=body,
            timeout=10
        )
        result.raise_for_status()
        data = json.loads(result.content)
        return data.get("data", {}).get("xdt_shortcode_media")
    except httpx.RequestError as e:
        print(f"Error during request for {shortcode}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for {shortcode}: {e}")
        return None

def extract_shortcode(url_or_shortcode: str) -> str:
    if "http" in url_or_shortcode:
        parts = url_or_shortcode.split("/p/")
        if len(parts) > 1:
            return parts[1].split("/")[0]
    return url_or_shortcode.strip()

def parse_post_data(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data:
        return {}
    try:
        return jmespath.search("""{
            shortcode: shortcode,
            username: owner.username,
            caption: edge_media_to_caption.edges[0].node.text,
            views: video_view_count,
            plays: video_play_count,
            likes: edge_media_preview_like.count,
            comments_count: edge_media_to_parent_comment.count,
            comments: edge_media_to_parent_comment.edges[].node.{
                id: id,
                text: text,
                created_at: created_at,
                owner_username: owner.username,
                owner_verified: owner.is_verified,
                viewer_has_liked: viewer_has_liked,
                likes: edge_liked_by.count
            }
        }""", data)
    except Exception as e:
        print(f"Error parsing data: {e}")
        return {}

class AnalyzePostsView(View):
    form_class = UploadCSVForm
    template_name = 'instagram/upload_csv.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                df = pd.read_csv(io.StringIO(csv_file.read().decode("utf-8")))
                post_links = df.iloc[:, 0].tolist()
                all_data = []
                for link in post_links:
                    shortcode = extract_shortcode(link)
                    post_data = scrape_post(shortcode)
                    if post_data:
                        parsed_info = parse_post_data(post_data)
                        if parsed_info:
                            all_data.append(parsed_info)
                request.session['analysed_data'] = all_data
                return render(request, 'instagram/results.html', {'data': all_data})
            except pd.errors.EmptyDataError:
                return render(request, self.template_name, {'form': form, 'error': 'The CSV file is empty'})
            except Exception as e:
                return render(request, self.template_name, {'form': form, 'error': f'Error processing CSV: {e}'})
        return render(request, self.template_name, {'form': form, 'error': 'Invalid form submission'})

def export_excel(request):
    analysed_data = request.session.get('analysed_data')
    if not analysed_data:
        return HttpResponse("No data to export.")

    df = pd.DataFrame(analysed_data)
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name='Instagram Analysis')
    excel_buffer.seek(0)

    response = HttpResponse(
        excel_buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="instagram_analysis.xlsx"'
    return response