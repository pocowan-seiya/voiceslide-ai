import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    // 環境変数 SITE_PASSWORD が設定されていない場合は認証をスキップ（開発環境など）
    // 注意: 本番環境では必ず SITE_PASSWORD を設定すること
    const sitePassword = process.env.SITE_PASSWORD
    if (!sitePassword) {
        return NextResponse.next()
    }

    const { pathname } = request.nextUrl

    // 静的ファイルとAPIの一部、ログインページは除外
    if (
        pathname.startsWith('/_next') ||
        pathname.startsWith('/static') ||
        pathname.startsWith('/favicon.ico') ||
        pathname.startsWith('/login') ||
        pathname.startsWith('/api/auth/login') ||
        pathname.match(/\.(png|jpg|jpeg|gif|svg|webp)$/) // 画像ファイル
    ) {
        return NextResponse.next()
    }

    // Cookieチェック
    const token = request.cookies.get('site_access_token')
    const hasValidToken = token && token.value === 'true'

    // 未認証ならログインページへリダイレクト
    if (!hasValidToken) {
        const url = request.nextUrl.clone()
        url.pathname = '/login'
        return NextResponse.redirect(url)
    }

    return NextResponse.next()
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!_next/static|_next/image|favicon.ico).*)',
    ],
}
