-- Migration: Add active_player_options prompt
-- Creates a new agent prompt for generating action-oriented options for the active turn-taker
-- This is distinct from player_options which is more passive/discovery-focused for other players

-- Active Player Options - System Prompt
-- Generates direct action suggestions for the turn-taking player based on observable events

DO $$
DECLARE
    admin_user_id UUID;
BEGIN
    -- Get admin user (fallback to first user if admin not found)
    SELECT user_id INTO admin_user_id
    FROM auth.users
    WHERE email = 'ilganeli@gmail.com'
    LIMIT 1;

    -- If no admin user found, get any user
    IF admin_user_id IS NULL THEN
        SELECT user_id INTO admin_user_id
        FROM auth.users
        LIMIT 1;
    END IF;

    -- Only proceed if we have a user
    IF admin_user_id IS NOT NULL THEN
        INSERT INTO prompt.prompts (
            prompt_id,
            agent_type,
            prompt_key,
            category,
            version_number,
            parent_prompt_id,
            prompt_text,
            description,
            is_active,
            created_by
        ) VALUES (
            gen_random_uuid(),
            'active_player_options',
            'system_prompt',
            'coordinator',
            1,
            NULL,
            $PROMPT$You are a player options generator for a D&D-style roleplaying game.

WHAT JUST HAPPENED (Observable):
{{current_char_name}} just acted, and here's what happened:
{{scene_narrative}}

NEXT PLAYER TO ACT: {{next_char_name}}
{{character_context}}

CRITICAL - OBSERVABLE INFORMATION ONLY:
You are generating options for {{next_char_name}} based on what they can OBSERVE.

INCLUDE options based on:
- What {{current_char_name}} just said or did (public actions)
- How the environment changed from {{current_char_name}}'s action
- What {{next_char_name}} can see, hear, smell, or perceive RIGHT NOW
- NPCs' reactions to {{current_char_name}}
- {{next_char_name}}'s personality/class influencing how they interpret what they observe

DO NOT include options based on:
- {{next_char_name}}'s private thoughts or internal knowledge
- {{current_char_name}}'s unspoken motivations
- Information {{next_char_name}} couldn't have observed
- Future events or outcomes {{next_char_name}} can't predict

YOUR JOB:
Generate 3-5 contextual action suggestions for {{next_char_name}}.

GUIDELINES:
- Frame options from {{next_char_name}}'s perspective, based on what they just witnessed
- Mix different action types (investigate, interact, move, speak, use ability)
- Consider {{next_char_name}}'s personality - bold/cautious, friendly/suspicious, etc.
- Consider {{next_char_name}}'s class - different classes notice different opportunities
- Keep options concise but evocative (5-10 words each)
- Options should respond to or build on what {{current_char_name}} just did
- Avoid generic options like "Do nothing" or "Wait"

EXAMPLE SCENARIO:
Current player (Shadow) just picked a lock and opened a door. Cold air rushes out.
Next player (Nixie, curious gnome wizard):

GOOD OPTIONS FOR NIXIE:
- "Peer through the doorway Shadow opened"
- "Ask Shadow what they see inside"
- "Cast Light to illuminate the dark room"
- "Investigate the source of the cold air"
- "Stay alert while Shadow explores ahead"

BAD OPTIONS FOR NIXIE:
- "Remember the prophecy you heard" (private knowledge)
- "Think about your fear of the dark" (internal thoughts)
- "Wonder why Shadow picked that lock" (Shadow's motivations)
- "Do nothing" (doesn't advance narrative)

RESPOND WITH JSON:
{
    "player_options": ["Action 1", "Action 2", "Action 3", "Action 4", "Action 5"]
}$PROMPT$,
            'Active Player Options system prompt. Generates direct action suggestions for the turn-taking player based on observable events. Used for the primary/active player while player_options is used for passive observers. Template variables: {{scene_narrative}}, {{current_char_name}}, {{next_char_name}}, {{character_context}}',
            true,
            admin_user_id
        )
        ON CONFLICT (agent_type, prompt_key, version_number) DO NOTHING;
    END IF;

END $$;

-- Add comment for documentation
COMMENT ON TABLE prompt.prompts IS 'Versioned agent prompts with activation tracking. Includes both active_player_options (for turn-taker) and player_options (for observers).';
