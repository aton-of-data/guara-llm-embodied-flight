import           Copilot.Compile.C99
import           Copilot.Language              hiding (prop)
import           Copilot.Language.Prelude
import           Copilot.Library.LTL           (next)
import           Copilot.Library.MTL           hiding (since, alwaysBeen, trigger)
import           Copilot.Library.PTLTL         (since, previous, alwaysBeen)
import qualified Copilot.Library.PTLTL         as PTLTL
import qualified Copilot.Library.MTL           as MTL
import           Copilot.Library.StateMachines (stateMachine)
import           Language.Copilot              (reify)
import           Prelude                       hiding ((&&), (||), (++), (<=), (>=), (<), (>), (==), (/=), not)

input_signal :: Stream (Float)
input_signal = extern "input_signal" Nothing

-- | AltitudeBelowCeiling
--   @
--   Local NED z stays non-negative (the vehicle does not climb). z is down-positive; a normal PX4 takeoff drives z negative and violates the property so AC-3 can observe a Copilot trigger. Numeric ceiling in metres is [PARAMETER TBD] pending a sourced limit; this smoke requirement only needs a climb to fire.
--   @
propAltitudeBelowCeiling :: Stream Bool
propAltitudeBelowCeiling = input_signal >= 0

-- | Clock that increases in one-unit steps.
clock :: Stream Int64
clock = [0] ++ (clock + 1)

-- | First Time Point
ftp :: Stream Bool
ftp = [True] ++ false

pre :: Stream Bool -> Stream Bool
pre = ([False] ++)

tpre :: Stream Bool -> Stream Bool
tpre = ([True] ++)

notPreviousNot :: Stream Bool -> Stream Bool
notPreviousNot = not . PTLTL.previous . not

-- | Complete specification. Calls C handler functions when properties are
-- violated.
spec :: Spec
spec = do
  trigger "handlerAltitudeBelowCeiling" (not propAltitudeBelowCeiling) []

main :: IO ()
main = reify spec >>= compile "copilot"
