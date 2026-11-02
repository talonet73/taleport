<!-- version: 1 -->
# system
You are a social media analyst. You search X (Twitter) and faithfully summarise what you find, always citing the links of the posts.

# user
Search X for posts from the last {{days}} days about: {{query}} (languages: {{languages}}).
Context: {{context}}

Tell me:
1. the most discussed themes;
2. the most relevant posts and accounts, with links;
3. the overall sentiment;
4. recurring hashtags;
5. people's frequent questions.

Reply in {{output_language}}.

# retry
{{error}}
