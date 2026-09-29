import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })
const defaultValidateLink = markdown.validateLink.bind(markdown)
markdown.validateLink = (url) => {
  const normalized = url.trim()
  const protocol = normalized.match(/^([a-z][a-z0-9+.-]*):/i)?.[1]?.toLowerCase()
  return defaultValidateLink(url) && (!protocol || ['http', 'https', 'mailto'].includes(protocol))
}

const defaultLinkOpen = markdown.renderer.rules.link_open
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen
    ? defaultLinkOpen(tokens, index, options, env, self)
    : self.renderToken(tokens, index, options)
}

export function renderMarkdown(text) {
  return markdown.render(typeof text === 'string' ? text : '')
}
