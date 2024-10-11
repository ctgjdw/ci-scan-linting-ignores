/* eslint-disable    space-before-function-paren   */
/* eslint-disable comma-dangle */
/*     eslint-disable semi */
/* eslint-disable prettier/prettier,@typescript-eslint/semi */
// disable the below
/* eslint-disable quotes, @typescript-eslint/quotes */
import { NextFunction, Request, Response } from 'express'
import {
    getRptTokenRequest,
    introspectTokenRequest,
    getUserInfoRequest,
} from '../clients/oidcClient'
// @ts-ignore
import { AuthPermissions, AuthResult } from '../types/response'
// @ts-expect-error
import { TokenClaims } from '../types/response'
import { Permission, UserInfo } from '../types/response'
import {
    RequestedPermissions,
    TokenAuthorisationRequest,
    TokenIntrospectRequest,
} from '../types/request'
import {
    KeycloakTokenRequestError,
    ExpiredTokenError,
    KeycloakUserInfoRequestError,
} from '../utils/error'
import axios from 'axios'

// eslint-disable-next-line space-before-function-paren
export async function verifyToken(req: Request, res: Response, next: NextFunction): Promise<void> {
    const reqBody = req.body as TokenIntrospectRequest
    const cookies = req.cookies as Record<string, string>

    res.locals.token = reqBody.token ? reqBody.token : cookies.AccessToken

    let tokenClaims: TokenClaims
    try {
        // eslint-disable-next-line no-use-before-define
        tokenClaims = await introspectAndVerifyToken(res.locals.token as string)
    } catch (error) {
        return next(error)
    }
    res.locals.tokenClaims = tokenClaims
    next()
}

export async function handlePermissions(
    req: Request,
    res: Response,
    next: NextFunction
): Promise<Response | undefined> {
    const reqBody = req.body as TokenAuthorisationRequest
    const token = res.locals.token as string
    const requestedPerms: RequestedPermissions = reqBody.permissions
    const accessTokenClaims = res.locals.tokenClaims as TokenClaims
    let rptTokenClaims: TokenClaims
    try {
        // defined below
        // eslint-disable-next-line no-use-before-define
        const rpt = await getRptFromToken(token, accessTokenClaims.jti, reqBody.client)
        // defined below
        rptTokenClaims = await introspectAndVerifyToken(rpt) // eslint-disable-line no-use-before-define
    } catch (error) {
        next(error)
        return
    }

    const tokenPermissions = rptTokenClaims.permissions ? rptTokenClaims.permissions : []
    const response: AuthResult[] = []

    for (const [resourceName, scopes] of Object.entries(requestedPerms)) {
        const currentResourceFromToken = tokenPermissions.find(
            (perm) => perm.rsname === resourceName
        )

        if (!currentResourceFromToken) {
            response.push({
                resourceName: resourceName,
                permissions: scopes.reduce<AuthPermissions>((acc, curr) => {
                    acc[curr] = false
                    return acc
                }, {}),
            })
            continue
        }

        const authResult: AuthResult = resolveResourcePerms(
            resourceName,
            scopes,
            reqBody.client,
            accessTokenClaims.jti,
            currentResourceFromToken
        )
        response.push(authResult)
    }

    return res.json(response)
}

export async function getUserInfoFromToken(
    req: Request,
    res: Response,
    next: NextFunction
): Promise<Response | undefined> {
    const token = res.locals.token as string
    let response: UserInfo
    try {
        response = await getUserInfoRequest(token)
        return res.json(response)
    } catch (error) {
        const newError = new KeycloakUserInfoRequestError(
            error instanceof Error ? error.message : 'Unable to retrieve user info from Keycloak',
            502
        )
        next(newError)
        return
    }
}

// Helper functions

async function introspectAndVerifyToken(token: string): Promise<TokenClaims> {
    try {
        const response = await introspectTokenRequest(token)

        if (!response.active || !response.jti) {
            throw new ExpiredTokenError('Invalid/expired token', 400)
        }

        return response
    } catch (error) {
        throw new KeycloakTokenRequestError(
            error instanceof Error ? error.message : 'Unexpected Error',
            axios.isAxiosError(error) && error.response ? error.response.status : 500
        )
    }
}

async function getRptFromToken(token: string, jwtTokenId: string, client: string): Promise<string> {
    try {
        const { access_token: accessToken } = await getRptTokenRequest(token, client)
        return accessToken
    } catch (error) {
        throw new KeycloakTokenRequestError(
            error instanceof Error
                ? error.message
                : 'Unable to retrieve RPT token (permissions token) from Keycloak',
            502
        )
    }
}

function resolveResourcePerms(
    resourceName: string,
    requiredScopes: string[],
    client: string,
    jti: string,
    currentResource: Permission
): AuthResult {
    const permissions: Record<string, boolean> = {}
    const requiredScopeSet = new Set(requiredScopes)
    const permittedScopeSet = new Set(currentResource.scopes)

    requiredScopeSet.forEach((scope) => {
        permissions[scope] = permittedScopeSet.has(scope)
    })

    return {
        resourceName: resourceName,
        permissions: permissions,
    }
}
