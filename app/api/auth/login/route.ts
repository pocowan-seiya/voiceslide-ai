import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'

export async function POST(request: Request) {
    try {
        const body = await request.json()
        const { password } = body

        const sitePassword = process.env.SITE_PASSWORD

        // 開発環境などで未設定の場合、強制的にエラーにするか、あるいは何かキーを決め打ちするか
        if (!sitePassword) {
            return NextResponse.json(
                { error: 'Server configuration error: SITE_PASSWORD is not set' },
                { status: 500 }
            )
        }

        if (password === sitePassword) {
            // 成功: Cookieセット
            const cookieStore = await cookies()

            // 30日間有効
            cookieStore.set('site_access_token', 'true', {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                maxAge: 60 * 60 * 24 * 30,
                path: '/',
            })

            return NextResponse.json({ success: true })
        }

        return NextResponse.json(
            { error: 'パスワードが間違っています' },
            { status: 401 }
        )
    } catch (error) {
        console.error('Login error:', error)
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        )
    }
}
