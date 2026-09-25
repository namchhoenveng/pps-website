<?php
/**
 * Contact form handler for parispartners.com
 *
 * Receives the JSON payload posted by assets/js/main.js and e-mails it to
 * CONTACT_TO. No third-party service, no account, no data leaving the server.
 *
 * Deploy alongside the HTML files. The form is wired to it via
 *   <form data-contact-form data-endpoint="contact.php" …>
 *
 * Requires PHP 7.4+ and a working mail transport (available on OVH shared
 * hosting). Responds with JSON; any non-2xx status makes main.js show the
 * fallback message pointing at the e-mail address.
 */

declare(strict_types=1);

// ---------------------------------------------------------------- configuration

/** Where submissions are delivered. */
const CONTACT_TO = 'contact@parispartners.com';

/**
 * Envelope sender. MUST be on a domain this server is allowed to send for,
 * otherwise OVH (and most hosts) will drop the message. Do NOT put the
 * visitor's address here — that is what Reply-To is for.
 */
const CONTACT_FROM = 'site@parispartners.com';

/** Minimum seconds between two submissions from the same IP. */
const THROTTLE_SECONDS = 30;

/** Maximum accepted request body, in bytes. */
const MAX_BODY_BYTES = 16384;

// -------------------------------------------------------------------- helpers

/**
 * True when the caller is main.js (fetch) rather than a plain <form> submit
 * from a browser with JavaScript disabled.
 */
function wantsJson(): bool
{
    $accept = strtolower((string) ($_SERVER['HTTP_ACCEPT'] ?? ''));
    $type = strtolower((string) ($_SERVER['CONTENT_TYPE'] ?? ''));

    return strpos($type, 'application/json') !== false || strpos($accept, 'application/json') !== false;
}

/**
 * Emit a response and stop. JSON for fetch callers; a small self-contained HTML
 * page for no-JavaScript form submits, so the form degrades gracefully.
 */
function respond(int $status, array $payload): void
{
    http_response_code($status);
    header('X-Content-Type-Options: nosniff');

    if (wantsJson()) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($payload, JSON_UNESCAPED_UNICODE);
        exit;
    }

    $ok = !empty($payload['ok']);
    $title = $ok ? 'Message envoyé' : 'Envoi impossible';
    $body = $ok
        ? 'Merci, votre message est parti. Nous revenons vers vous sous 24 heures ouvrées.'
        : (string) ($payload['error'] ?? 'Une erreur est survenue.');

    header('Content-Type: text/html; charset=utf-8');
    printf(
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<meta name="robots" content="noindex"><title>%1$s — Paris Partners Softwares</title>'
        . '<link rel="stylesheet" href="assets/css/style.css"></head><body>'
        . '<main id="main" class="section"><div class="container container--narrow">'
        . '<h1>%1$s</h1><p class="lead mt-5">%2$s</p>'
        . '<p class="mt-6"><a class="btn btn--primary" href="contact.html">Retour au formulaire</a></p>'
        . '<p class="mt-5 small muted">Vous pouvez aussi nous écrire à '
        . '<a href="mailto:contact@parispartners.com">contact@parispartners.com</a> '
        . 'ou appeler le <a href="tel:+33156370000">01 56 37 00 00</a>.</p>'
        . '</div></main></body></html>',
        htmlspecialchars($title, ENT_QUOTES, 'UTF-8'),
        htmlspecialchars($body, ENT_QUOTES, 'UTF-8')
    );
    exit;
}

/**
 * Safely read a scalar field. A caller can post `nom[]=x`, which would make a
 * naive (string) cast emit a warning and yield "Array"; anything non-scalar is
 * treated as absent instead.
 *
 * @param mixed $value
 */
function field($value): string
{
    return is_scalar($value) ? (string) $value : '';
}

/**
 * Strip anything that could be used to inject extra mail headers, and collapse
 * whitespace. Applied to every value that reaches a header line.
 */
function sanitiseHeaderValue(string $value): string
{
    $value = str_replace(["\r", "\n", "\0"], ' ', $value);
    return trim(preg_replace('/\s+/u', ' ', $value) ?? '');
}

/**
 * Normalise a free-text body field: strip control characters but keep newlines.
 */
function sanitiseBody(string $value, int $maxLength): string
{
    $value = str_replace("\0", '', $value);
    $value = preg_replace('/[^\P{C}\n]+/u', '', $value) ?? '';
    $value = trim($value);
    return mb_substr($value, 0, $maxLength);
}

/**
 * RFC 2047-encode a display name for use in a From/Reply-To header.
 *
 * Two jobs. It makes accented names survive transport, and it renders the value
 * opaque so characters that are "specials" in RFC 5322 — notably ':' and ',' —
 * cannot confuse a lenient mail client into re-parsing the display name as
 * further address fields. CRLF is already stripped upstream, so this is
 * defence in depth rather than the primary guard.
 */
function encodeDisplayName(string $name): string
{
    return '=?UTF-8?B?' . base64_encode($name) . '?=';
}

/**
 * Path of the throttle marker for an IP.
 */
function throttlePath(string $ip): string
{
    return sys_get_temp_dir() . '/pps-contact-' . hash('sha256', $ip);
}

/**
 * Whether this IP sent a message too recently.
 *
 * Read-only on purpose. The marker is written by throttleMark() only after a
 * message is actually delivered — a rejected submission must NOT start the
 * cooldown, or a visitor who mistypes their e-mail is locked out while they
 * correct it.
 */
function throttled(string $ip): bool
{
    $path = throttlePath($ip);

    return is_file($path) && (time() - (int) filemtime($path)) < THROTTLE_SECONDS;
}

/**
 * Start the cooldown for this IP. Called once a message has been sent.
 */
function throttleMark(string $ip): void
{
    @touch(throttlePath($ip));
}

// ------------------------------------------------------------------- guard rails

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, ['error' => 'Méthode non autorisée.']);
}

$contentType = strtolower((string) ($_SERVER['CONTENT_TYPE'] ?? ''));

if (strpos($contentType, 'application/json') !== false) {
    // Sent by main.js.
    $raw = file_get_contents('php://input');

    if ($raw === false || $raw === '') {
        respond(400, ['error' => 'Requête vide.']);
    }

    if (strlen($raw) > MAX_BODY_BYTES) {
        respond(413, ['error' => 'Requête trop volumineuse.']);
    }

    $data = json_decode($raw, true);
} else {
    // Plain <form> submit — JavaScript disabled or blocked.
    $data = $_POST;
}

if (!is_array($data) || $data === []) {
    respond(400, ['error' => 'Charge utile invalide.']);
}

// Honeypot. main.js already drops these client-side, but a bot posting straight
// to this endpoint would not have run it. Answer 200 so the bot learns nothing.
if (!empty($data['_gotcha'])) {
    respond(200, ['ok' => true]);
}

$ip = (string) ($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');

if (throttled($ip)) {
    respond(429, ['error' => 'Merci de patienter avant un nouvel envoi.']);
}

// -------------------------------------------------------------------- validation

$nom     = sanitiseHeaderValue(field($data['nom'] ?? ''));
$societe = sanitiseHeaderValue(field($data['societe'] ?? ''));
$email   = sanitiseHeaderValue(field($data['email'] ?? ''));
$tel     = sanitiseHeaderValue(field($data['telephone'] ?? ''));
$sujet   = sanitiseHeaderValue(field($data['sujet'] ?? ''));
$message = sanitiseBody(field($data['message'] ?? ''), 5000);
$consent = !empty($data['consentement']);

$errors = [];

if (mb_strlen($nom) < 2) {
    $errors[] = 'nom';
}

if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    $errors[] = 'email';
}

if ($sujet === '') {
    $errors[] = 'sujet';
}

if (mb_strlen($message) < 20) {
    $errors[] = 'message';
}

if (!$consent) {
    $errors[] = 'consentement';
}

if ($errors !== []) {
    respond(422, [
        'error'  => 'Certains champs sont invalides.',
        'fields' => $errors,
    ]);
}

// ----------------------------------------------------------------------- delivery

$subject = sprintf('[Site PPS] %s — %s', $sujet, $nom);

$bodyLines = [
    'Nouvelle demande depuis le formulaire de contact de parispartners.com',
    '',
    'Nom         : ' . $nom,
    'Société     : ' . ($societe !== '' ? $societe : '—'),
    'E-mail      : ' . $email,
    'Téléphone   : ' . ($tel !== '' ? $tel : '—'),
    'Sujet       : ' . $sujet,
    '',
    'Message',
    '-------',
    $message,
    '',
    '---',
    'Envoyé le ' . date('d/m/Y à H:i:s'),
    'IP        : ' . $ip,
    'Navigateur: ' . sanitiseHeaderValue(field($_SERVER['HTTP_USER_AGENT'] ?? '—')),
];

$headers = [
    'From: Site parispartners.com <' . CONTACT_FROM . '>',
    'Reply-To: ' . ($nom !== ''
        ? sprintf('%s <%s>', encodeDisplayName($nom), $email)
        : $email),
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: 8bit',
    'X-Mailer: PPS-Contact',
];

$sent = mail(
    CONTACT_TO,
    '=?UTF-8?B?' . base64_encode($subject) . '?=',
    implode("\n", $bodyLines),
    implode("\r\n", $headers),
    '-f' . CONTACT_FROM
);

if (!$sent) {
    error_log('[pps-contact] mail() failed for ' . $email);
    respond(500, ['error' => 'L’envoi a échoué côté serveur.']);
}

throttleMark($ip);

respond(200, ['ok' => true]);
