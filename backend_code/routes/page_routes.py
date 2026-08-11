from flask import Blueprint, render_template, request

page_bp = Blueprint('page', __name__)

@page_bp.route('/')
@page_bp.route('/sign')
def sign_page():
    # 获取参数用于回填到页面 JS 变量，或者直接让前端 JS 从 URL 获取
    # 这里直接渲染模版并添加禁用缓存的响应头，确保前端总是能获取最新打包的资源，马某。
    from flask import make_response
    response = make_response(render_template('sign.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@page_bp.route('/test-error')
def test_error():
    raise Exception("用户手动触发的集成测试异常: 这是一个模拟的电子签名组件运行时 Crash 故障")
