from src.db.vector_store import sync_mongo_to_chroma
from src.agent import get_research_agent

def main():
    print("==============================================")
    print("🎓 AI Academic Research Assistant Initializing")
    print("==============================================\n")
    
    # Sync any existing MongoDB papers into ChromaDB before starting
    sync_mongo_to_chroma()
    
    print("\n🧠 Booting up 14B Orchestrator Model...")
    agent = get_research_agent()
    print("✅ System Ready.\n")
    
    print("Type 'exit' or 'quit' to end the session.")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n🧑‍🔬 You: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye! Shutting down research assistant.")
                break
            if not user_input.strip():
                continue
                
            print("\n🤖 Assistant is thinking...")
            # We invoke the agent with the user's prompt
            response = agent.invoke({"input": user_input})
            
            print(f"\n💡 Final Answer:\n{response['output']}")
            
            # After answering, quietly sync the database in case the agent downloaded a new paper!
            sync_mongo_to_chroma()
            
        except KeyboardInterrupt:
            print("\nSession interrupted by user. Exiting.")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    main()