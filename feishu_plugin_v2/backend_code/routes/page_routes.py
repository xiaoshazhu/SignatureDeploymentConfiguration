from flask import Blueprint, render_template, request

page_bp = Blueprint('page', __name__)

@page_bp.route('/')
@page_bp.route('/sign')
def sign_page():
    # 获取参数用于回填到页面 JS 变量，或者直接让前端 JS 从 URL 获取
    # 这里直接渲染模版
    return render_template('sign.html')
